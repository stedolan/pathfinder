from __future__ import with_statement
import os, os.path
import stat
import shutil
import glob
import datetime
import pwd, grp
import hashlib
import sys
import re
import tempfile
from contextlib import contextmanager

class FileMode:
    def __init__(self, mode):
        self.mode = mode
        
    
    def _fmt(self, r, w, x, spec, specl):
        xbit = {(True,  True ): specl,
                (True,  False): "x",
                (False, True ): specl.upper(),
                (False, False): "-"}
        return "%s%s%s" % (
            "r" if r else "-",
            "w" if w else "-",
            xbit[(bool(x),bool(spec))])

    def __nonzero__(self):
        return self.mode != 0

    def _selbits(self, fields):
        b = 0
        for f in fields.split():
            b |= getattr(stat, f)
        return FileMode(self.mode & b)
    
    @property
    def user(self):
        return self._selbits("S_ISUID S_IRUSR S_IWUSR S_IXUSR")

    @property
    def group(self):
        return self._selbits("S_ISGID S_IRGRP S_IWGRP S_IXGRP")
    
    @property
    def other(self):
        return self._selbits("S_ISVTX S_IROTH S_IWOTH S_IXOTH")

    @property
    def world(self):
        return self.other

    @property
    def setuid(self):
        return self._selbits("S_ISUID")
    
    @property
    def setgid(self):
        return self._selbits("S_ISGID")

    @property
    def read(self):
        return self._selbits("S_IRUSR S_IRGRP S_IROTH")
    
    @property
    def write(self):
        return self._selbits("S_IWUSR S_IWGRP S_IWOTH")
    
    @property
    def execute(self):
        return self._selbits("S_IXUSR S_IXGRP S_IXOTH S_ISUID S_ISGID")

    def __repr__(self):
        m = self.mode
        modestr = "-" + \
            self._fmt(m & stat.S_IRUSR, m & stat.S_IWUSR, m & stat.S_IXUSR,
                      m & stat.S_ISUID, "s") + \
            self._fmt(m & stat.S_IRGRP, m & stat.S_IWGRP, m & stat.S_IXGRP,
                      m & stat.S_ISGID, "s") + \
            self._fmt(m & stat.S_IROTH, m & stat.S_IWOTH, m & stat.S_IXOTH,
                      m & stat.S_ISVTX, "t")
        return "<%04o %s>" % (self.mode, modestr)

class path(object):
    def __init__(self, p, rest = None):
        if isinstance(p, path):
            p = p.path
        if isinstance(rest, path):
            rest = rest.path
        if rest is not None:
            p = os.path.join(p, rest)
        self.path = os.path.normpath(p)
        
    def __div__(self, other):
        return path(self.path, other)
    def __truediv__(self, other):
        return path(self.path, other)
    def __rdiv__(self, other):
        return path(other, self.path)
    def __rtruediv__(self, other):
        return path(other, self.path)

    def __mod__(self, other):
        return self.relative_to(other)

    def __rmod__(self, other):
        return path(other).relative_to(self)

    #cwd = path(".")
        
    def relative_to(self, p):
        p = path(p)
        if not (p.is_absolute and self.is_absolute):
            raise Exception()
        return path(os.path.relpath(self.path, p.path))

    def __iter__(self):
        for i in os.listdir(self.path):
            yield self[i]

    def __getitem__(self, dirent):
        return path(self.path, dirent)

    def __eq__(self, other):
        ## FIXME!!!
        return self.path == path(other).path

    def __repr__(self):
        last_bad_path = None
        for p in [self] + self.parents:
            try:
                stat = os.lstat(p.path)
                break
            except OSError, ex:
                last_bad_path = p.path

        if last_bad_path == self.path:
            return '<Path "%s" (does not exist)>' % self.path
        elif last_bad_path != None:
            return '<Path "%s" (invalid, "%s" does not exist)' % \
                (self.path, last_bad_path)
        else:
            return '<%s "%s">' % (self.type(stat), self.path)
        
        
        return '<Path "%s">' % self.path

    def __len__(self):
        # FIXME: this is not the fastest
        return len(os.listdir(self.path))

    @property
    def size(self):
        return os.stat(self.path).st_size 
    
    @property
    def parent(self):
        return path(os.path.dirname(self.path))

    @property
    def basename(self):
        return os.path.basename(self.path)

    @property
    def extension(self):
        return os.path.splitext(self.path)[1]

    @property
    def drive(self):
        return os.path.splitdrive(self.path)[0]

    @property
    def realpath(self):
        return path(os.path.abspath(self.path))
    

    @property
    def children(self):
        return list(self)

    @property
    def parents(self):
        p = self.path
        parts = []
        while True:
            newp, curr = os.path.split(p)
            if newp == p and curr == '':
                break
            else:
                p = newp
                parts.append(path(p))
        return parts

    def type(self, statres):
        types = {
            stat.S_IFBLK: "blockdev",
            stat.S_IFDIR: "directory",
            stat.S_IFLNK: "symlink",
            stat.S_IFREG: "file",
            stat.S_IFCHR: "chardev",
            stat.S_IFIFO: "fifo",
            stat.S_IFSOCK: "socket"
            }
        fmt = stat.S_IFMT(statres.st_mode)
        if fmt in types:
            return types[fmt].title()
        else:
            return "unknown"

    @property
    def is_absolute(self):
        return os.path.isabs(self.path)

    @property
    def is_directory(self):
        return os.path.isdir(self.path)

    @property
    def is_file(self):
        return os.path.isfile(self.path)

    @property
    def is_symlink(self):
        return os.path.islink(self.path)

    @property
    def last_access_time(self):
        return datetime.datetime.fromtimestamp(os.path.getatime(self.path))

    @property
    def last_modify_time(self):
        return datetime.datetime.fromtimestamp(os.path.getmtime(self.path))

    @property
    def last_metadata_change_time(self):
        return datetime.datetime.fromtimestamp(os.path.getctime(self.path))        

    @property
    def owner(self):
        return pwd.getpwuid(self.owner_uid).pw_name
    
    @property
    def owner_uid(self):
        return os.lstat(self.path).st_uid

    @property
    def owned(self):
        return os.getuid() == self.owner_uid

    @property
    def group(self):
        return grp.getgrgid(self.group_gid).gr_name

    @property
    def group_gid(self):
        return os.lstat(self.path).st_gid

    @property
    def perms(self):
        return FileMode(stat.S_IMODE(os.lstat(self.path).st_mode))

    @property
    def link_target(self):
        return path(os.readlink(self.path))

    @property
    def final_link_target(self):
        s = set()
        p = self
        while p.is_symlink:
            if p.path in s:
                raise IOError("Recursive symlinks at %s" % self.path)
            s.add(p.path)
            p = p.link_target
        return p
        
    
    @property
    def empty(self):
        if self.is_directory:
            return len(self) == 0
        elif self.is_file:
            return self.size == 0
        else:
            raise OSError("Neither a file or directory: %s" % self.path)

    def newer_than(self, other):
        other = path(other)
        return other.mtime < self.mtime

    def older_than(self, other):
        other = path(other)
        return self.mtime < other.mtime

    @property
    def readable(self):
        return os.access(self.path, os.R_OK)
    
    @property
    def writable(self):
        return os.access(self.path, os.W_OK)
    
    @property
    def executable(self):
        return os.access(self.path, os.X_OK)

    @property
    def exists(self):
        return os.access(self.path, os.F_OK)


    def glob(self, pattern):
        return map(path, glob.glob(os.path.join(self.path, pattern)))

    def remove(self, recurse=False):
        if self.is_directory:
            if recurse:
                shutil.rmtree(self.path)
            else:
                os.rmdir(self.path)
        else:
            os.remove(self.path)

    def rename_to(self, newpath):
        # FIXME rel names, short names, slash-less newpaths
        newpath = path(newpath)
        os.rename(self.path, newpath.path)
        return newpath

    def symlink(self, linkpath):
        linkpath = path(linkpath)
        os.symlink(self.path, linkpath.path)
        return linkpath

    def hardlink(self, linkpath):
        linkpath = path(linkpath)
        os.link(self.path, linkpath.path)
        return linkpath

    def mkdir(self, name = None, recurse_up = False):
        if name is not None:
            p = path(os.path.join(self.path, name))
        else:
            p = self
        if recurse_up:
            os.makedirs(p.path)
        else:
            os.mkdir(p.path)
        return p

    def chown(self, user = None, group = None):
        if group is None and user is None:
            raise Exception("chown must be passed a user or a group or both")

        if group is None:
            group = os.stat(self.path).st_gid
        elif isinstance(group, basestring):
            group = grp.getgrnam(group).gr_gid

        if user is None:
            user = os.stat(self.path).st_uid
        elif isinstance(user, basestring):
            user = pwd.getpwuid(user).pw_uid
        
        os.chown(self.path, user, group)

    def chgrp(self, newgrp):
        self.chown(group = newgrp)
        

    def open(self, mode="rb"):
        return filehandle(open(self.path, mode), self)

    def write(self, contents):
        f = self.open("w+")
        f.write(str(contents))
        f.close()

    def append(self, contents):
        f = self.open("a+")
        f.write(str(contents))
        f.close()

    def read(self, size = -1):
        f = self.open()
        s = f.read(size)
        f.close()
        return s

    contents = property(read, write)


    @contextmanager
    def atomic_update(self):
        if not self.is_file:
            raise Exception()
        try:
            fd, p = tempfile.mkstemp(dir = self.parent.path,
                                     prefix = ".tmp",
                                     suffix = ".%d" % os.getpid())
            fd = os.fdopen(fd, "w+b")
            p = path(p)
            yield fd
            fd.close()
            p.rename_to(self)
        finally:
            fd.close()
            if p.exists:
                p.remove()

    def chdir(self):
        os.chdir(self.path)


    def adv_patterns(self, patterns, name):
        subp = set()
        for p in patterns:
            while len(p) and p[0] == "**":
                subp.add(p)
                p = p[1:]
            if p == ():
                subp.add(p)
            elif isinstance(p[0],basestring):
                if p[0] == name:
                    subp.add(p[1:])
            elif p[0].match(name):
                subp.add(p[1:])
        return subp

    def recwalk(self, inc_patterns, inc_fns, ex_patterns, ex_fns, visit_dirs, maxdepth):
        if maxdepth < 0:
            return

        if () in ex_patterns or any(f(self) for f in ex_fns):
            return


        curr_match = () in inc_patterns or any(f(self) for f in inc_fns)

        if len(inc_patterns) == 0 and not curr_match:
            return



        if not self.is_directory:
            if curr_match:
                yield self
            return

        if curr_match and visit_dirs == 'before':
            yield self
        
        selfmatch = set([()])

        for sub in self:
            subpats = set()
            name = sub.basename
            for result in sub.recwalk(self.adv_patterns(inc_patterns - selfmatch, name),
                                      inc_fns,
                                      self.adv_patterns(ex_patterns, name),
                                      ex_fns,
                                      visit_dirs,
                                      maxdepth - 1):
                yield result

        if curr_match and visit_dirs == 'after':
            yield self



    def compile_glob_pattern(self, pat, ignore_case):
        pat = pat.replace("\\", "/")
        absolute = pat.startswith("/")

        def compile_fnmatch_pattern(pat):
            if pat == "**":
                return pat
            if not any(c in pat for c in "*[?"):
                return pat
            regex = "^"
            while pat:
                if pat.startswith("*"):
                    regex += ".*"
                    pat = pat[1:]
                elif pat.startswith("?"):
                    regex += "."
                    pat = pat[1:]
                elif pat.startswith("["):
                    neg = pat[1] in "!^"
                    if neg:
                        pat = pat[2:]
                    else:
                        pat = pat[1:]
                    p = pat.index("]",1)
                    regex += "[" + ("^" if neg else "") + pat[:p] + "]"
                    pat = pat[p+1:]
                else:
                    regex += re.escape(pat[0])
                    pat = pat[1:]
            regex += "\Z"
            rflags = re.S
            if ignore_case:
                rflags |= re.IGNORECASE
            return re.compile(regex, rflags)
    
        pat = [compile_fnmatch_pattern(p) for p in pat.split("/") if len(p) > 0]
        if len(pat) == 0:
            pat = ["**"]
        elif not absolute and pat[0] != "**":
            pat = ["**"] + pat
        return tuple(pat)

    def find(self, include="**", exclude=[], ignore_case = False, visit_dirs = 'before', max_depth = 1000):
        if isinstance(include, basestring) or callable(include):
            include = [include]
        if isinstance(exclude, basestring) or callable(exclude):
            exclude = [exclude]
        inc_pat = [self.compile_glob_pattern(p, ignore_case) 
                   for p in include if not callable(p)]
        inc_fn = [p for p in include if callable(p)]
        ex_pat = [self.compile_glob_pattern(p, ignore_case)
                  for p in exclude if not callable(p)]
        ex_fn = [p for p in exclude if callable(p)]
        return self.recwalk(set(inc_pat), inc_fn, set(ex_pat), ex_fn, visit_dirs, max_depth)


    def hash_with(self, hashfn):
        f = self.open()
        while True:
            data = f.read(2**16)
            if not data:
                break
            hashfn.update(data)
        f.close()
        return hashfn.hexdigest()

    @property
    def md5(self):
        return self.hash_with(hashlib.md5())

    @property
    def sha1(self):
        return self.hash_with(hashlib.sha1())
    
    @property
    def sha224(self):
        return self.hash_with(hashlib.sha224())
    
    @property
    def sha256(self):
        return self.hash_with(hashlib.sha256())
    
    @property
    def sha384(self):
        return self.hash_with(hashlib.sha384())
    
    @property
    def sha512(self):
        return self.hash_with(hashlib.sha512())




class filehandle(object):
    def __init__(self, fileobj, path = None):
        self.fileobj = fileobj
        self.auto_flush = True
        self.path = path

    @property
    def pos(self):
        return self.fileobj.tell()

    @pos.setter
    def pos(self, value):
        if value < 0:
            self.fileobj.seek(value, os.SEEK_END)
        else:
            self.fileobj.seek(value, os.SEEK_SET)

    def fileno(self):
        return self.fileobj.fileno()

    @property
    def length(self):
        # fixme
        return os.fstat(self.fileno()).st_size

    def skip(self, n):
        self.fileobj.seek(n, os.SEEK_CUR)

    def close(self):
        self.fileobj.close()

    def _slicerange(self, item):
        if not isinstance(item, slice) or item.step not in [None,1]:
            raise TypeError("Files can only be indexed with slices of step 1")
        start, stop = item.start or 0, item.stop or self.length
        if (start < 0 and stop < 0) or (start >= 0 and stop >= 0):
            pos, length = (start, stop - start)
        elif start < 0:
            pos, length = start, -self.length + stop - start
        else:
            pos, length = start, self.length + stop - start
        if length < 0:
            raise TypeError("File can't be indexed with slice of negative length")
        return pos, length

    def read(self, n):
        return self.fileobj.read(n)

    def write(self, data):
        self.fileobj.write(data)
        if self.auto_flush:
            self.flush()

    def flush(self):
        self.fileobj.flush()

    def sync(self, data_only = False):
        self.flush()
        if data_only:
            os.fdatasync(self.fileno())
        else:
            os.fsync(self.fileno())

    def set_contents(self, data):
        self.pos = 0
        self.truncate(0)
        self.write(data)

    def append(self, data):
        # FIXME: should use fcntl to set O_APPEND
        self.fileobj.seek(0, os.SEEK_END)
        self.write(data)

    def truncate(self, size = 0):
        self.fileobj.truncate(size)

    def __getitem__(self, item):
        if item == Ellipsis:
            raise TypeError("Can't read file[...]")
        pos, length = self._slicerange(item)
        oldpos = self.pos
        self.pos = pos
        data = self.read(length)
        self.pos = oldpos
        return data

    def isatty(self):
        return self.fileobj.isatty()

    @property
    def closed(self):
        return self.fileobj.closed

    @property
    def name(self):
        return self.path.path


    def __setitem__(self, item, data):
        if item == Ellipsis:
            self.append(data)
        elif item == slice(None, None, None):
            self.set_contents(data)
        else:
            pos, length = self._slicerange(item)
            if len(data) != length:
                raise TypeError("New data must be the same length as old")
            oldpos = self.pos
            self.pos = pos
            self.write(data)
            self.pos = oldpos
        


#Path("asdf").walk(include=["/etc/*", "foo/*"], lambda f: f.size > 10 * 1024 * 1024)
