# 2025/6/26 Hiroyuki Ogasawara
# vim:ts=4 sw=4 et:

import os
import sys

# S base_url http://localhost:11343
# ======== default
# S model       qwen3:14b
# I num_ctx     16384
# F temperature 0.7
# A tools       calc_add get_weather
# ====T header
# ～
# ====T system_prompt
# ～
# ====T base_prompt
# ～

# S prset    assistant
# A env      MCP_PROJECT_ROOT=c:/project MCP_ENGINE_ROOT=c:/engine
# ====T system
# ～
# ====T prompt
# ～
# ====T header
# ～

#------------------------------------------------------------------------------

class TextLoader:
    TYPE_DICT= '========'
    TYPE_TEXT= '====T'
    def __init__( self ):
    	pass

    def load_text( self, lines, index ):
        line_count= len(lines)
        text= ''
        while index < line_count:
            line= lines[index]
            if line.startswith( ';;' ):
                continue
            if line.startswith( '====' ):
                return  text,index
            text+= line
            index+= 1
        return  text,index

    def load_dict( self, lines, index, map_obj ):
        line_count= len(lines)
        while index < line_count:
            line= lines[index].strip()
            if line == '' or line.startswith( ';;' ):
                index+= 1
                continue
            params= line.split()
            param_type= params[0]
            if param_type == 'S':
                map_obj[params[1]]= params[2]
            elif param_type == 'I':
                map_obj[params[1]]= int(params[2])
            elif param_type == 'F':
                map_obj[params[1]]= float(params[2])
            elif param_type == 'A':
                map_obj[params[1]]= params[2:]
            elif param_type == self.TYPE_TEXT:
                text,index= self.load_text( lines, index+1 )
                map_obj[params[1]]= text
                continue
            elif param_type == self.TYPE_DICT:
                return  index
            else:
                print( 'dict "%s" format error (%d):' % (param_type,index), line )
            index+= 1
        return  index

    def load( self, file_name ):
        if not os.path.exists( file_name ):
            return  None
        print( 'load:', file_name )
        with open( file_name, 'r', encoding='utf-8' ) as fi:
            lines= fi.readlines()
        map_obj= {}
        line_count= len(lines)
        index= self.load_dict( lines, 0, map_obj )
        while index < line_count:
            line= lines[index].strip()
            if line == '' or line.startswith( ';;' ):
                index+= 1
                continue
            params= line.split()
            param_type= params[0]
            if param_type == self.TYPE_DICT:
                prev_obj= {}
                map_obj[params[1]]= prev_obj
                index= self.load_dict( lines, index+1, prev_obj )
                continue
            else:
                print( 'type "%s" error (%d):' % (param_type,index), line )
            index+= 1
        return  map_obj

#------------------------------------------------------------------------------

def main( argv ):
    file_name= None
    acount= len(argv)
    ai= 1
    while ai< acount:
        arg= argv[ai]
        if arg[0] == '-':
            pass
        else:
            file_name= arg
        ai+= 1
    loader= TextLoader()
    obj= loader.load( file_name )
    print( obj )
    return  0

if __name__=='__main__':
    sys.exit( main( sys.argv ) )


