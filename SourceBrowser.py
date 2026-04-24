# vim:ts=4 sw=4 et:

import os
import sys
import re
import shutil
import subprocess
import fnmatch

lib_path= os.path.dirname(__file__)
if lib_path not in sys.path:
    sys.path.append( lib_path )
import Functions

_RG= shutil.which( 'rg' )
_SKIP_DIRS= frozenset( ['.git', '__pycache__', 'Intermediate', 'Binaries', 'DerivedDataCache', 'Saved'] )
_MAX_LIST= 500
_MAX_SEARCH= 500

def _get_root():
    return os.environ.get( 'MCP_FOLDER_ROOT', os.environ.get( 'MCP_SOURCE_ROOT', '' ) )

def _validate_path( root, rel_path ):
    abs_root= os.path.realpath( root )
    if not rel_path or rel_path == '.':
        return abs_root
    candidate= os.path.realpath( os.path.join( abs_root, rel_path ) )
    if candidate == abs_root or candidate.startswith( abs_root + os.sep ):
        return candidate
    return None

def _parse_extensions( ext_str ):
    if not ext_str:
        return None
    exts= set()
    for e in ext_str.split( ',' ):
        e= e.strip()
        if e:
            if not e.startswith( '.' ):
                e= '.' + e
            exts.add( e.lower() )
    return exts or None

#------------------------------------------------------------------------------

def _list_files_impl( directory, ext_set, recursive ):
    results= []
    root_len= len( directory ) + 1
    truncated= [False]

    def scan( path ):
        if truncated[0]:
            return
        try:
            with os.scandir( path ) as it:
                for entry in it:
                    if truncated[0]:
                        return
                    if entry.name in _SKIP_DIRS:
                        continue
                    if entry.is_dir( follow_symlinks=False ):
                        if recursive:
                            scan( entry.path )
                    elif entry.is_file( follow_symlinks=False ):
                        if ext_set:
                            _, ext= os.path.splitext( entry.name )
                            if ext.lower() not in ext_set:
                                continue
                        results.append( entry.path[root_len:] )
                        if len( results ) >= _MAX_LIST:
                            truncated[0]= True
                            return
        except PermissionError:
            pass

    scan( directory )
    return results, truncated[0]

@Functions.tool.add
def list_files( directory: str, extension: str, recursive: bool ) -> str:
    """
    List files in the specified directory within the source root.

    Args:
        directory: Relative path from the source root. Use empty string for the root directory.
        extension: Comma-separated extensions to filter, e.g. ".cpp,.h". Use empty string for all files.
        recursive: If true, list files in subdirectories recursively.
    """
    root= _get_root()
    if not root:
        return 'MCP_FOLDER_ROOT is not set'
    target= _validate_path( root, directory )
    if target is None:
        return 'Invalid path: "%s"' % directory
    if not os.path.isdir( target ):
        return 'Directory not found: "%s"' % directory
    ext_set= _parse_extensions( extension )
    files, truncated= _list_files_impl( target, ext_set, recursive )
    if not files:
        return 'No files found'
    note= ' (showing first %d)' % _MAX_LIST if truncated else ''
    header= '**Files in "%s"** (%d%s):\n\n' % ( directory or '.', len( files ), note )
    return header + '\n'.join( '- ' + f for f in files )

#------------------------------------------------------------------------------

def _rg_search( pattern, root, target, ext_set, case_sensitive, cap ):
    cmd= [_RG, '--line-number', '--no-heading', '--color=never', '--max-columns=300']
    if not case_sensitive:
        cmd.append( '--ignore-case' )
    if ext_set:
        for ext in ext_set:
            cmd.extend( ['--glob', '*' + ext] )
    cmd.extend( ['--', pattern, target] )
    try:
        proc= subprocess.run( cmd, capture_output=True, text=True, encoding='utf-8',
                              errors='replace', timeout=30 )
        if proc.returncode == 2:
            return None, False
        root_prefix= root + os.sep
        lines= []
        for line in proc.stdout.splitlines():
            lines.append( line[len( root_prefix ):] if line.startswith( root_prefix ) else line )
        truncated= len( lines ) > cap
        return lines[:cap], truncated
    except subprocess.TimeoutExpired:
        return [], False

def _python_search( pattern, root, target, ext_set, case_sensitive, cap ):
    flags= 0 if case_sensitive else re.IGNORECASE
    try:
        pat= re.compile( pattern, flags )
    except re.error as e:
        return 'Pattern error: ' + str( e ), False
    root_len= len( root ) + 1
    results= []
    for dirpath, dirs, files in os.walk( target ):
        dirs[:]= [d for d in dirs if d not in _SKIP_DIRS]
        for name in files:
            if ext_set:
                _, ext= os.path.splitext( name )
                if ext.lower() not in ext_set:
                    continue
            full= os.path.join( dirpath, name )
            try:
                with open( full, 'r', encoding='utf-8', errors='ignore' ) as f:
                    for lineno, line in enumerate( f, 1 ):
                        if pat.search( line ):
                            results.append( '%s:%d:%s' % ( full[root_len:], lineno, line.rstrip() ) )
                            if len( results ) >= cap:
                                return results, True
            except OSError:
                continue
    return results, False

@Functions.tool.add
def search_text( pattern: str, directory: str, extension: str, case_sensitive: bool, max_results: int ) -> str:
    """
    Search for text patterns in source files and return matching lines with file paths and line numbers.
    Uses ripgrep if installed for fast searching, otherwise falls back to a Python implementation.
    Patterns support regular expressions.

    Args:
        pattern: Regular expression pattern to search for.
        directory: Relative path from the source root to limit the search scope. Use empty string to search all.
        extension: Comma-separated extensions to filter, e.g. ".cpp,.h". Use empty string for all file types.
        case_sensitive: Set to false to ignore case.
        max_results: Maximum number of matching lines to return. Recommended: 50-200.
    """
    root= _get_root()
    if not root:
        return 'MCP_FOLDER_ROOT is not set'
    target= _validate_path( root, directory )
    if target is None:
        return 'Invalid path: "%s"' % directory
    ext_set= _parse_extensions( extension )
    cap= min( max_results, _MAX_SEARCH )

    results= None
    truncated= False
    if _RG:
        results, truncated= _rg_search( pattern, root, target, ext_set, case_sensitive, cap )
    if results is None:
        results, truncated= _python_search( pattern, root, target, ext_set, case_sensitive, cap )
    if isinstance( results, str ):
        return results

    if not results:
        return 'No matches found for "%s"' % pattern
    note= ', truncated' if truncated else ''
    header= '**Results for "%s"** (%d matches%s):\n\n' % ( pattern, len( results ), note )
    return header + '\n'.join( results )

#------------------------------------------------------------------------------

def _resolve_file( root, file_path ):
    candidate= _validate_path( root, file_path )
    if candidate and os.path.isfile( candidate ):
        return candidate
    base= os.path.basename( file_path ).lower()
    if not base or base in ( '.', '..' ):
        return None
    for dirpath, dirs, files in os.walk( root ):
        dirs[:]= [d for d in dirs if d not in _SKIP_DIRS]
        for name in files:
            if name.lower() == base:
                return os.path.join( dirpath, name )
    return None

@Functions.tool.add
def read_file_range( file_path: str, start_line: int, line_count: int ) -> str:
    """
    Read a range of lines from a source file with line numbers.
    Can locate files by filename alone, partial path, or full path relative to the source root.
    Line numbers in the output allow precise follow-up reads of adjacent sections.
    If multiple files share the same filename, the first match is returned; use a more specific path to disambiguate.

    Args:
        file_path: File name or relative path. A bare filename triggers an automatic search.
        start_line: First line to read (1-based). Use 1 to start from the beginning.
        line_count: Number of lines to read. Use 0 to read the entire file.
    """
    root= _get_root()
    if not root:
        return 'MCP_FOLDER_ROOT is not set'
    full= _resolve_file( root, file_path )
    if full is None:
        return 'File not found: "%s"' % file_path
    try:
        with open( full, 'r', encoding='utf-8', errors='ignore' ) as f:
            lines= f.readlines()
    except OSError as e:
        return 'Cannot read file: %s' % str( e )
    total= len( lines )
    s= max( 0, start_line - 1 )
    end= total if line_count <= 0 else min( total, s + line_count )
    selected= lines[s:end]
    rel= full[len( root ) + 1:]
    header= '** File: %s  lines %d-%d / %d **\n\n' % ( rel, s + 1, s + len( selected ), total )
    return header + ''.join( '%5d  %s' % ( s + i + 1, line ) for i, line in enumerate( selected ) )

#------------------------------------------------------------------------------

@Functions.tool.add
def find_files( name_pattern: str, directory: str ) -> str:
    """
    Find files by filename pattern. Supports wildcards (* matches any characters, ? matches one character).
    Returns paths relative to the source root.

    Args:
        name_pattern: Filename pattern with optional wildcards. e.g. "*DebugMenu*", "*.Build.cs", "Player*.h"
        directory: Relative path from the source root to search in. Use empty string to search all.
    """
    root= _get_root()
    if not root:
        return 'MCP_FOLDER_ROOT is not set'
    target= _validate_path( root, directory )
    if target is None:
        return 'Invalid path: "%s"' % directory
    pat= name_pattern.lower()
    root_len= len( root ) + 1
    results= []
    truncated= False
    for dirpath, dirs, files in os.walk( target ):
        dirs[:]= [d for d in dirs if d not in _SKIP_DIRS]
        for name in files:
            if fnmatch.fnmatch( name.lower(), pat ):
                results.append( os.path.join( dirpath, name )[root_len:] )
                if len( results ) >= _MAX_LIST:
                    truncated= True
                    break
        if truncated:
            break
    if not results:
        return 'No files found matching "%s"' % name_pattern
    note= ' (showing first %d)' % _MAX_LIST if truncated else ''
    header= '**Files matching "%s"** (%d%s):\n\n' % ( name_pattern, len( results ), note )
    return header + '\n'.join( '- ' + f for f in results )

