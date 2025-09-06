# 2025/06/08 Ogasawara Hiroyuki
# vim:ts=4 sw=4 et:

import os
import inspect
import random
import re
import time

#------------------------------------------------------------------------------

class ToolManager:
    def __init__( self ):
        self.info_list= []
        self.func_map= {}
        self.debug_echo= False

    def get_function_info( self, func ):
        type_to_name= {
            'int': 'integer',
            'str': 'string',
            'bool': 'boolean',
            'float': 'number',
        }
        func_info= {
            'name': func.__name__,
            'description': func.__doc__,
            'parameters': {
                'type': 'object',
                'properties': {}
            }
        }
        sig= inspect.signature( func )
        properties= {}
        required= []
        for param_name,param in sig.parameters.items():
            param_type= 'string'
            if param.annotation != inspect._empty:
                param_type= param.annotation.__name__
                if param_type in type_to_name:
                    param_type= type_to_name[param_type]
            properties[param_name]= {
                'type': param_type,
            }
            required.append( param_name )
        if len(properties) > 0:
            func_info['parameters']['properties']= properties
            func_info['parameters']['required']= required
        return  { 'type': 'function', 'function': func_info }

    def add( self, func ):
        func_info= self.get_function_info( func )
        self.func_map[func.__name__]= func_info,func
        if self.debug_echo:
            print( 'Add: Function "%s"' % func.__name__, func.__doc__ )
        return  func

    def select_tools( self, name_list ):
        tool_list= []
        for name in name_list:
            if name in self.func_map:
                print( 'Add: Function "%s"' % name )
                tool_list.append( self.func_map[name][0] )
        self.info_list= tool_list

    def get_tools( self ):
        return  self.info_list

    def call_func( self, func_name, args ):
        if func_name not in self.func_map:
            return  'Function "%s" not found' % func_name
        func_info,func= self.func_map[func_name]
        try:
            result= str(func( **args ))
        except TypeError as e:
            return  'Argument mismatch in tool call. "%s"' % (str(e))
        if self.debug_echo:
            if len(result) <= 128:
                print( 'Call: %s(%s) result=%s' % (func_name,str(args),result), flush=True )
            else:
                print( 'Call: %s(%s) result=%d chars' % (func_name,str(args),len(result)), flush=True )
        return  result

tool= ToolManager()

def get_tools():
    return  tool

#------------------------------------------------------------------------------

@tool.add
def calc_add( a: int, b: int ) -> int:
    """Add two numbers"""
    return  a + b

@tool.add
def get_weather( city:str ) -> str:
    """Get the weather"""
    return  ['晴れ','雨','雷雨','曇り','雪','曇のち晴れ'][random.randrange(0,6)]

#------------------------------------------------------------------------------

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

@tool.add
def read_source_code( file_name:str ) -> str:
    """
    Read a source code.
    By simply specifying the file name, you can search the Project and Engine folders and read the file content.
    """
    folder_list= []
    folder_root= os.environ.get( 'MCP_FOLDER_ROOT', os.environ.get( 'MCP_SOURCE_ROOT', '' ) )
    if folder_root != '':
        folder_list.append( folder_root )
    project_root= os.environ.get( 'MCP_PROJECT_ROOT', '' )
    if project_root != '':
        folder_list.append( os.path.join( project_root, 'Source' ) )
        folder_list.append( os.path.join( project_root, 'Plugins' ) )
    engine_root= os.environ.get( 'MCP_ENGINE_ROOT', '' )
    if engine_root != '':
        folder_list.append( os.path.join( engine_root, 'Engine/Source' ) )
        folder_list.append( os.path.join( engine_root, 'Engine/Plugins' ) )
    ignore_set= set( ['.','..'] )
    base_name= os.path.basename( file_name )
    if base_name in ignore_set:
        return  'Invalid filename "%s"' % file_name
    full_name= search_file( folder_list, base_name )
    print( 'load:', full_name, flush=True )
    if os.path.exists( full_name ):
        with open( full_name, 'r', encoding='utf-8' ) as fi:
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

@tool.add
def read_source_code3( file_name:str ) -> str:
    """
    Read a source code.
    By simply specifying a partial path or filename, you can search the folders and read the file content.
    """
    folder_list= []
    folder_root= os.environ.get( 'MCP_FOLDER_ROOT', os.environ.get( 'MCP_SOURCE_ROOT', '' ) )
    if folder_root != '':
        folder_list.append( os.path.abspath( folder_root ) )
    project_root= os.environ.get( 'MCP_PROJECT_ROOT', '' )
    if project_root != '':
        project_root= os.path.abspath( project_root )
        folder_list.append( os.path.join( project_root, 'Source' ) )
        folder_list.append( os.path.join( project_root, 'Plugins' ) )
    engine_root= os.environ.get( 'MCP_ENGINE_ROOT', '' )
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
        with open( full_name, 'r', encoding='utf-8' ) as fi:
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

@tool.add
def search_in_files( pattern:str, case_sensitive:bool=True, include_filenames:bool=False ) -> str:
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
    folder_root= os.environ.get( 'MCP_FOLDER_ROOT', '' )
    return  grep_files( folder_root, pat_key, include_filenames, True )

#------------------------------------------------------------------------------

@tool.add
def get_current_datetime() -> str:
    """
    Returns the current date and time in the format YYYY-MM-DD HH:MM:SS."
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

#------------------------------------------------------------------------------

class LocalMemory:
    def __init__( self ):
        self.memory= []

    def append( self, title, content ):
        index= len(self.memory)
        self.memory.append( (index,title,content) )
        return  index

    def get_memory( self, memory_id ):
        if index >= 0 and index < len(self.memory) and self.memory[index] is not None:
            return  self.memory[index]
        return  -1,'Empty','Empty'

    def remove( self, index ):
        if index >= 0 and index < len(self.memory):
            self.memory[index]= None

local_memory= LocalMemory()

@tool.add
def add_note( title:str, content:str ) -> str:
    """
    Adds a note with the given title and content to retain critical information.
    Used to preserve values, keywords, intermediate thoughts, or summaries
    of past interactions as context grows.

    Args:
        title: Title of the note
        content: Content of the note
    """
    global local_memory
    note_id= local_memory.append( title, content )
    return  'Added: ntoe_id=%d' % note_id

@tool.add
def get_note( ntoe_id:int ) -> str:
    """
    Retrieves a note by its unique ID.

    Args:
        note_id: Unique identifier assigned when the note was added.
    """
    global local_memory
    _,title,content= local_memory.get_memory( note_id )
    return  '# ' + title + '\n\n' + content + '\n'

@tool.add
def get_note_list() -> str:
    """
    Returns a list of note entries with their ids and titles.
    """
    result= '# Notes\n\n'
    global local_memory
    for note in local_memory.memory:
        if note:
            result+= '- %d : %s\n' % (note[0],note[1])
    return  result

@tool.add
def delete_note( note_id:int ) -> str:
    """
    Deletes a note by its id.

    Args:
        note_id: The id of the note to be deleted.
    """
    global local_memory
    local_memory.remove( note_id )
    return  'Deleted: note_id=%d' % note_id

#------------------------------------------------------------------------------
