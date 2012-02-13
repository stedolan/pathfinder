
pathfinder - pythonic filesystem library
==========

Python's standard library includes many, many modules for dealing with
files. Ironically, none of these are particularly "pythonic". 

There's os, which among other things can create, delete and move
files. To copy them, you'll need shutil's copy or copy2 (slightly
different, of course). To list files, you might use the os or the glob
modules. You can get file metadata with os.stat, but you'll have to
use an entirely different module to interpret its results. 

pathfinder uses these standard modules to make a library that can be
used without constant reference to the documentation.

It's currently alpha software. I'm using the "one giant file" method
of distribution, so you can install it by putting pathfinder.py somewhere
handy. There'll be a proper pip package soon!

It's all slightly unix-flavoured at the moment. It sits on top of the
cross-platform primitives provided by Python, so it should
more-or-less work on Windows, but this hasn't been tested.

pathfinder is licensed under the MIT license.

paths
=====

A ''path'' represents a file, which may or may not exist.
 
    >>> p = path('/home/stephen/coding/pathfinder/pathfinder.py')

You can do lots of things with path objects

    >>> if p.exists:
    ...     print p.owner, p.last_modify_time
    stephen 2012-02-12 15:40:20.328579

If you have a path object for a directory, you can use the / operator
to look at things inside the directory.

    >>> p = path('/home/stephen/coding')
    >>> print p / 'pathfinder'
    <Directory "/home/stephen/coding/pathfinder">
    >>> print p / 'pathfinder' / 'pathfinder.py'
    <File "/home/stephen/coding/pathfinder/pathfinder.py">
    
'/' interprets the second argument relative to the first, so

    >>> path('/home/stephen') / 'coding/pathfinder'
    <Directory "/home/stephen/coding/pathfinder">
    >>> path('/home/stephen') / '/etc/passwd'
    <File "/etc/passwd">
    
'%' is its inverse, and gives you the first path as a relative path
from the second.
    
    >>> path('/home/stephen/coding/pathfinder') % '/home/stephen'
    <Directory 'coding/pathfinder'>
    >>> path('/home/stephen/coding/pathfinder') % '/etc'
    <Directory '../home/stephen/coding/pathfinder'>
    
You can list things in a directory by just iterating over the object.

    >>> for f in p:
    ...     print f.basename
    .git
    .gitignore
    README.markdown
    README.markdown~
    pathfinder.py
    pathfinder.py~
    pathfinder.pyc
    
or by using the more advanced ''.find'' method (see below)

    >>> for f in p.find("Pathfinder*", 
    ...                 exclude=["*~", "*.pyc", ".git"], 
    ...                 ignore_case=True):
    pathfinder.py



Manipulating the filesystem
===========================

You can inspect a path with path.exists, path.is_directory, path.is_file,
path.is_symlink, path.size and various others. 

path.last_modify_time returns an actual Python datetime object. For
symlinks, path.link_target shows where they point, and
path.final_link_target follows as many steps are necessary to get to
the end of a chain of symlinks.

    >>> if path('README.markdown').newer_than(path('pathfinder.py')):
    ...     print "whatever the hell you just did, document it!"

You can modify the filesystem with path.mkdir(), path.symlink(),
path.chown() and friends. path.chown can be used to change the user or
group or both, and takes either a numeric ID or a name.

    >>> p.chown(user = "stephen", group = "stephen")


Unix permissions
----------------

''.owner'' and ''.group'' give the owner and group of a file as
strings (use ''.owner_uid'') and (''.group_uid'') for numeric IDs.

    >>> path('/etc/passwd').group
    'root'

''.perms'' will give the unix permissions of the file at a particular
path.

    >>> path('/etc/passwd').perms
    <0644 -rw-r--r-->

perms.user will restrict show only the user permissions, perms.write
only the write permissions, and so on. So, we can find all
world-executable setuid root programs in '/bin' with:

    >>> [f for f in path('/bin') 
         if f.perms.world.execute and f.perms.setuid and f.owner == 'root']
    [<File "/bin/ping6">,
     <File "/bin/fusermount">,
     <File "/bin/su">,
     <File "/bin/mount">,
     <File "/bin/umount">,
     <File "/bin/ping">]



Reading and writing
===================

pathfinder provides the absolute easiest method ever of reading and
writing files.

    >>> p = path('myfile')
    >>> p.contents = "Look at me! I'm a file!"
    >>> print p.contents
    Look at me! I'm a file!

You can also go the traditional route and open the file:

    >>> f = path('myfile').open("r")

What you get back is a ''pathfinder.filehandle'' object, which is just
a little bit more awesome than a standard Python file. It implements
the standard Python file methods (so you can pass it to things that
expect a "file-like object").

You can seek around and read and write parts of a filehandle:

    >>> f = path('myfile').open("w+")
    >>> f.write("Hello world")
    >>> print f[0:5]
    "Hello"
    >>> f[6:11] = "again"
    >>> print f[:]
    "Hello again"
    


Atomic update
-------------

There's a nice technique for modifying a file, where instead of
directly writing the file you create a new file, write that one, then
change its name to the target filename and replace the original. On
Unix-y systems, this is guaranteed atomic: any other program will see
either the entire old file or the entire new file, never a
half-written file or a missing file.

On Windows, it's not atomic but still useful: no other process will
see a half-written file, although they may observe a missing file in
the instant during the file move.

Using pathfinder and Python's with statement, this is easily done:

    >>> with mypath.atomic_update() as f:
    ...     f.write('lots of interesting data')
    ...     f.write('and some more')

"f" will point to a temporary file in the same directory as 'mypath',
and at the end of the 'with' statement the new file will replace the
old. If the code in the with statement throws an exception, or the
Python process mysteriously dies, then the old file will remain intact.


Finding stuff
=============

pathfinder offers a friendlier alternative to the slightly awkward
os.walk and the deeply unpleasant os.path.walk.

    >>> p = path('/home/stephen/coding')
    >>> p.find(include = ["*.py", "docs/**/*.html"],
               exclude = ".git",
               visit_dirs = "before",
               ignore_case = True,
               max_depth = 3)

* include specifies what to search for, as a list of string
patterns. The patterns can contain wildcards: "?" matches any
single character, "\*" any sequence of characters and "\*\*" any sequence
of directories. So, the pattern "coding/\*/\*.html" matches
"coding/project1/info.html" but not "coding/project1/docs/help.html",
while "coding/\*\*/\*.html" matches both. Patterns may also be specified
as callables, which will be invoked to determine whether a file is
worth returning. If there's only one pattern, it need not be passed in
a list.

* exclude is much the same, but specifies paths to avoid. Excluded paths
won't even be recursed into.

* visit_dirs can be 'before', 'after' or False, and specifies whether
directories are returned before or after their contents, or not at
all.

* ignore_case and max_depth should hopefully be reasonably clear. :)

find returns an iterator yielding path objects.
