# vim:ts=4 sw=4 et:

import os
import sys
import re
import shutil
import subprocess
import fnmatch
from collections import OrderedDict

lib_path= os.path.dirname(__file__)
if lib_path not in sys.path:
    sys.path.append( lib_path )
from Functions import get_toolbox,ToolEnv

_RG= shutil.which( 'rg' )
_SKIP_DIRS= frozenset( ['.git', '__pycache__', 'Intermediate', 'Binaries', 'DerivedDataCache', 'Saved'] )
_MAX_LIST= 500
_MAX_SEARCH= 500

def _get_root( env ):
    return env.get( 'MCP_FOLDER_ROOT', env.get( 'MCP_SOURCE_ROOT', '' ) )

def _validate_path( root, rel_path ):
    abs_root= os.path.realpath( root )
    if not rel_path or rel_path == '.':
        return abs_root
    candidate= os.path.realpath( os.path.join( abs_root, rel_path ) )
    if candidate == abs_root or candidate.startswith( abs_root + os.sep ):
        return candidate
    return None

def _parse_patterns( pattern_str ):
    if not pattern_str:
        return None
    pats= []
    for p in pattern_str.split( ',' ):
        p= p.strip().lower()
        if p:
            pats.append( p )
    return pats or None

def _match_filename( name_lower, patterns ):
    if patterns is None:
        return True
    for pat in patterns:
        if fnmatch.fnmatch( name_lower, pat ):
            return True
    return False

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

def _list_files_impl( base, patterns, recursive ):
    pairs= []
    truncated= [False]
    base_len= len( base ) + 1

    def scan( path ):
        if truncated[0]:
            return
        try:
            entries= list( os.scandir( path ) )
        except PermissionError:
            return
        files_here= []
        sub_dirs= []
        for entry in entries:
            if entry.name in _SKIP_DIRS:
                continue
            if entry.is_dir( follow_symlinks=False ):
                sub_dirs.append( entry.path )
            elif entry.is_file( follow_symlinks=False ):
                if _match_filename( entry.name.lower(), patterns ):
                    files_here.append( entry.name )
        files_here.sort()
        rel_dir= path[base_len:] if path != base else ''
        for fname in files_here:
            pairs.append( ( rel_dir, fname ) )
            if len( pairs ) >= _MAX_LIST:
                truncated[0]= True
                return
        if recursive:
            sub_dirs.sort()
            for sd in sub_dirs:
                if truncated[0]:
                    return
                scan( sd )

    scan( base )
    return pairs, truncated[0]

def _format_grouped( pairs, header_path, truncated ):
    if not pairs:
        return 'No files found'
    groups= OrderedDict()
    for rel_dir, fname in pairs:
        groups.setdefault( rel_dir, [] ).append( fname )
    note= ' (showing first %d)' % _MAX_LIST if truncated else ''
    out= ['**Files in "%s"** (%d files in %d dirs%s):' % (
            header_path or '.', len( pairs ), len( groups ), note )]
    out.append( '' )
    for rel_dir, names in groups.items():
        out.append( rel_dir + '/' if rel_dir else './' )
        for n in names:
            out.append( '  ' + n )
    return '\n'.join( out )

mcp= get_toolbox()

@mcp.tool()
def list_files( env:ToolEnv, directory: str, pattern: str, recursive: bool ) -> str:
    """
    List files in the specified directory within the source root.
    Files are grouped by their containing folder. The full path of each file is "<folder>/<filename>".

    Args:
        directory: Relative path from the source root. Use empty string for the root directory.
        pattern: Comma-separated filename wildcard patterns. e.g. "*.cpp,*.h", "*skill*.md", "Player*". Use empty string to list all files.
        recursive: If true, list files in subdirectories recursively.
    """
    root= _get_root( env )
    if not root:
        return 'MCP_FOLDER_ROOT is not set'
    target= _validate_path( root, directory )
    if target is None:
        return 'Invalid path: "%s"' % directory
    if not os.path.isdir( target ):
        return 'Directory not found: "%s"' % directory
    patterns= _parse_patterns( pattern )
    pairs, truncated= _list_files_impl( target, patterns, recursive )
    return _format_grouped( pairs, directory, truncated )

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

@mcp.tool()
def search_text( env:ToolEnv, pattern: str, directory: str, extension: str, case_sensitive: bool, max_results: int ) -> str:
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
    root= _get_root( env )
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

@mcp.tool()
def read_file_range( env:ToolEnv, file_path: str, start_line: int, line_count: int ) -> str:
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
    root= _get_root( env )
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



def main():
    result= list_files( os.environ, 'skills', 'jenkins_skill.md', False )
    print( result )
    result= read_file_range( os.environ, 'jenkins_skill.md', 1, 5 )
    print( result )

if __name__=='__main__':
    main()

