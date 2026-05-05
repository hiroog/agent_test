# 2025/06/08 Ogasawara Hiroyuki
# vim:ts=4 sw=4 et:

import os
import sys
import random

lib_path= os.path.dirname(__file__)
if lib_path not in sys.path:
    sys.path.append( lib_path )
from Functions import get_toolbox

#------------------------------------------------------------------------------

mcp= get_toolbox()

@mcp.tool()
def calc_add( a: int, b: int ) -> int:
    """Add two numbers"""
    return  a + b

@mcp.tool()
def get_weather( city:str ) -> str:
    """Get the weather"""
    return  ['晴れ','雨','雷雨','曇り','雪','曇のち晴れ'][random.randrange(0,6)]


