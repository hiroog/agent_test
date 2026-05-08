# 2025/06/08 Ogasawara Hiroyuki
# vim:ts=4 sw=4 et:

import os
import re
import sys

lib_path= os.path.dirname(__file__)
if lib_path not in sys.path:
    sys.path.append( lib_path )
from Functions import get_toolbox

#------------------------------------------------------------------------------

mcp= get_toolbox()

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

@mcp.tool()
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

@mcp.tool()
def get_note( ntoe_id:int ) -> str:
    """
    Retrieves a note by its unique ID.

    Args:
        note_id: Unique identifier assigned when the note was added.
    """
    global local_memory
    _,title,content= local_memory.get_memory( note_id )
    return  '# ' + title + '\n\n' + content + '\n'

@mcp.tool()
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

@mcp.tool()
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

