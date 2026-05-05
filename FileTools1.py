# 2025/06/08 Ogasawara Hiroyuki
# vim:ts=4 sw=4 et:

import os
import re
import sys

lib_path= os.path.dirname(__file__)
if lib_path not in sys.path:
    sys.path.append( lib_path )
from Functions import get_toolbox,ToolEnv

#------------------------------------------------------------------------------

mcp= get_toolbox()

def find_file( folder, base_name ):
    for root,dirs,files in os.walk( folder ):
        for name in files:
            if base_name == name.lower():
                return  os.path.join( root, name )
    return  None

def search_file( search_list, base_name ):
    base_name_low= base_name.lower()
    for dir_name in search_list:
        result= find_file( dir_name, base_name_low )
        if result:
            return  result
    return  base_name

@mcp.tool()
def read_source_code( env:ToolEnv, file_name:str ) -> str:
    """
    Read a source code.
    By simply specifying the file name, you can search the Project and Engine folders and read the file content.
    """
    folder_list= []
    folder_root= env.get( 'MCP_FOLDER_ROOT', env.get( 'MCP_SOURCE_ROOT', '' ) )
    if folder_root != '':
        folder_list.append( folder_root )
    project_root= env.get( 'MCP_PROJECT_ROOT', '' )
    if project_root != '':
        folder_list.append( os.path.join( project_root, 'Source' ) )
        folder_list.append( os.path.join( project_root, 'Plugins' ) )
    engine_root= env.get( 'MCP_ENGINE_ROOT', '' )
    if engine_root != '':
        folder_list.append( os.path.join( engine_root, 'Engine/Source' ) )
        folder_list.append( os.path.join( engine_root, 'Engine/Plugins' ) )
    print( 'project:', env.get( 'MCP_PROJECT_ROOT', '' ) )
    print( 'folder:', env.get( 'MCP_FOLDER_ROOT', '' ) )
    print( 'engine:', env.get( 'MCP_ENGINE_ROOT', '' ) )
    print( 'source:', env.get( 'MCP_SOURCE_ROOT', '' ) )
    print( 'list:', folder_list, flush=True )
    ignore_set= set( ['.','..'] )
    base_name= os.path.basename( file_name )
    if base_name in ignore_set:
        return  'Invalid filename "%s"' % file_name
    full_name= search_file( folder_list, base_name )
    print( 'load:', full_name, flush=True )
    if os.path.exists( full_name ):
        with open( full_name, 'r', encoding='utf-8', errors='replace' ) as fi:
            code= fi.read()
        return  ('** File: %s **\n\n' % base_name) + code
    print( 'not found:', full_name, flush=True )
    return  'File "%s" not found' % file_name

#------------------------------------------------------------------------------

def find_path3( folder, file_name ):
    for root,dirs,files in os.walk( folder ):
        full_path= os.path.join( root, file_name )
        if os.path.exists( full_path ):
            return  full_path
    return  None

def search_path3( folder_list, file_name ):
    file_name= file_name.replace( '\\', '/' ).lower()
    if os.path.isabs( file_name ):
        found= False
        for folder in folder_list:
            folder= folder.replace( '\\', '/' ).lower()
            if file_name.startswith( folder ):
                return  file_name
        return  None
    for folder in folder_list:
        result= find_path3( folder, file_name )
        if result:
            return  result
    return  None

@mcp.tool()
def read_source_code3( env:ToolEnv, file_name:str ) -> str:
    """
    Read a source code.
    By simply specifying a partial path or filename, you can search the folders and read the file content.
    """
    folder_list= []
    folder_root= env.get( 'MCP_FOLDER_ROOT', env.get( 'MCP_SOURCE_ROOT', '' ) )
    if folder_root != '':
        folder_list.append( os.path.abspath( folder_root ) )
    project_root= env.get( 'MCP_PROJECT_ROOT', '' )
    if project_root != '':
        project_root= os.path.abspath( project_root )
        folder_list.append( os.path.join( project_root, 'Source' ) )
        folder_list.append( os.path.join( project_root, 'Plugins' ) )
    engine_root= env.get( 'MCP_ENGINE_ROOT', '' )
    if engine_root != '':
        engine_root= os.path.abspath( engine_root )
        folder_list.append( os.path.join( engine_root, 'Engine/Source' ) )
        folder_list.append( os.path.join( engine_root, 'Engine/Plugins' ) )
    ignore_set= set( ['.','..'] )
    base_name= os.path.basename( file_name )
    if base_name in ignore_set:
        return  'Invalid filename "%s"' % file_name
    if '..' in file_name:
        return  'Invalid path "%s"' % file_name
    full_name= search_path3( folder_list, file_name )
    if full_name is None:
        full_name= search_file( folder_list, base_name )
    print( 'load:', full_name, flush=True )
    if os.path.exists( full_name ):
        with open( full_name, 'r', encoding='utf-8', errors='replace' ) as fi:
            code= fi.read()
        return  ('** File: %s **\n\n' % base_name) + code
    print( 'not found:', full_name, flush=True )
    return  'File "%s" not found' % file_name

#------------------------------------------------------------------------------

def grep_files( folder, pat_key, filename, content ):
    result_text= '**Found documents**:\n\n'
    found_files= 0
    root_length= len(folder)+1
    for root,dirs,files in os.walk( folder ):
        if '.git' in root:
            continue
        if '__pycache__' in root:
            continue
        for name in files:
            full_path= os.path.join( root, name )
            relative_path= full_path[root_length:]
            if filename:
                pat= pat_key.search( relative_path )
                if pat:
                    result_text+= '- %s\n' % relative_path
                    found_files+= 1
                    continue
            if content:
                with open( full_path, 'r', encoding='utf-8', errors='ignore' ) as fi:
                    data= fi.read()
                    pat= pat_key.search( data )
                    if pat:
                        result_text+= '- %s\n' % relative_path
                        found_files+= 1
    if found_files == 0:
        result_text= 'File not found\n\n'
    return  result_text

@mcp.tool()
def search_in_files( env:ToolEnv, pattern:str, case_sensitive:bool=True, include_filenames:bool=False ) -> str:
    """
    Searches documents and file contents and returns a list of filenames of found files.
    Search patterns can use Python's regular expressions.

    Args:
        pattern: Regular expressions
        case_sensitive: If false, case sensitivity is ignored. The default is true.
        include_filenames: If true, include filenames.
    """
    flags= 0
    if not case_sensitive:
        flags|= re.IGNORECASE
    try:
        pat_key= re.compile( pattern, flags )
    except re.error as e:
        return  str(e)
    folder_root= env.get( 'MCP_FOLDER_ROOT', env.get( 'MCP_SOURCE_ROOT', '' ) )
    return  grep_files( folder_root, pat_key, include_filenames, True )

#------------------------------------------------------------------------------

