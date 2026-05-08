# 2025/6/26 Hiroyuki Ogasawara
# vim:ts=4 sw=4 et:

import os
import sys

# S base_url http://localhost:11343
# ======== default
# S model       qwen3:14b
# I num_ctx     16384
# F temperature 0.7
# SA tools      calc_add get_weather
# ====T header
# ～
# ====T system_prompt
# ～
# ====T base_prompt
# ～

# S prset    assistant
# SA env     MCP_PROJECT_ROOT=c:/project MCP_ENGINE_ROOT=c:/engine
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
        self.bool_set= set(['true','1','True'])

    def load_text( self, lines, index ):
        line_count= len(lines)
        text= ''
        while index < line_count:
            line= lines[index]
            if line.startswith( ';;' ):
                index+= 1
                continue
            if line.startswith( '====' ):
                return  text,index
            text+= line
            index+= 1
        return  text,index

    def load_dict( self, lines, index, map_obj, dict_indent ):
        dict_type= '=' * dict_indent
        line_count= len(lines)
        while index < line_count:
            line= lines[index].strip()
            if line == '' or line.startswith( ';;' ):
                index+= 1
                continue
            params= line.split()
            param_type= params[0]
            if param_type == 'S':
                map_obj[params[1]]= line[len(params[1])+2:].strip()
            elif param_type == 'I':
                map_obj[params[1]]= int(params[2])
            elif param_type == 'B':
                map_obj[params[1]]= params[2] in self.bool_set
            elif param_type == 'F':
                map_obj[params[1]]= float(params[2])
            elif param_type == 'A' or param_type == 'SA':
                map_obj[params[1]]= params[2:]
            elif param_type == self.TYPE_TEXT:
                text,index= self.load_text( lines, index+1 )
                map_obj[params[1]]= text
                continue
            elif param_type == dict_type:
                child_obj= {}
                map_obj[params[1]]= child_obj
                index= self.load_dict( lines, index+1, child_obj, dict_indent+2 )
                continue
            elif param_type.startswith( self.TYPE_DICT ) and len(param_type) < dict_indent:
                return  index
            else:
                print( 'dict "%s" format error (%d):' % (param_type,index), line )
            index+= 1
        return  index

    def load( self, file_name ):
        if not os.path.exists( file_name ):
            return  None
        with open( file_name, 'r', encoding='utf-8', errors='ignore' ) as fi:
            lines= fi.readlines()
        map_obj= {}
        self.load_dict( lines, 0, map_obj, 8 )
        return  map_obj

    def save_dict( self, fo, obj, dict_indent ):
        for key in obj:
            val= obj[key]
            if type(val) is str:
                if '\n' not in val:
                    fo.write( 'S %s %s\n' % (key, val) )
            elif type(val) is int:
                fo.write( 'I %s %d\n' % (key, val) )
            elif type(val) is float:
                fo.write( 'F %s %f\n' % (key, val) )
            elif type(val) is bool:
                fo.write( 'B %s %s\n' % (key, 'true' if val else 'false') )
            elif type(val) is list:
                fo.write( 'A %s ' % key )
                for v in val:
                    fo.write( ' ' + v )
                fo.write( '\n' )
        for key in obj:
            val= obj[key]
            if type(val) is str:
                if '\n' in val:
                    fo.write( self.TYPE_TEXT + ' %s\n' % key )
                    fo.write( val )
                    if len(val) >= 1 and val[-1] != '\n':
                        fo.write( '\n' )
        dict_type= '=' * dict_indent
        for key in obj:
            val= obj[key]
            if type(val) is dict:
                fo.write( '%s %s\n' % (dict_type,key) )
                self.save_dict( fo, val, dict_indent+2 )

    def save( self, file_name, obj ):
        with open( file_name, 'w', encoding='utf-8' ) as fo:
            self.save_dict( fo, obj, 8 )

#------------------------------------------------------------------------------

def usage():
    print( 'TextLoader v1.00 Hiroyuki Ogasawara' )
    print( 'usage: TextLoader [options] <input_file>' )
    print( 'options:' )
    print( '  -o <output_file>' )
    print( '  --test' )
    sys.exit( 1 )

def load_object( file_name ):
    if file_name.lower().endswith( '.json' ):
        import json
        with open( file_name, 'r', encoding='utf-8', errors='replace' ) as fi:
            return  json.loads( fi.read() )
    return  TextLoader().load( file_name )

def save_object( file_name, obj ):
    if file_name.lower().endswith( '.json' ):
        import json
        with open( file_name, 'w', encoding='utf-8' ) as fo:
            fo.write( json.dumps( obj, ensure_ascii=False, indent=4 ) )
    else:
        TextLoader().save( file_name, obj )

def main( argv ):
    output_name= None
    file_name= None
    test_mode= False
    acount= len(argv)
    ai= 1
    while ai< acount:
        arg= argv[ai]
        if arg[0] == '-':
            if arg == '-o':
                if ai+1 < acount:
                    ai+= 1
                    output_name= argv[ai]
            elif arg == '--test':
                test_mode= True
            else:
                usage()
        else:
            file_name= arg
        ai+= 1

    if test_mode:
        obj= load_object( file_name )
        text_name= 'loader.output.txt'
        json_name= 'loader.output.json'
        save_object( text_name, obj )
        save_object( json_name, obj )
        obj2= load_object( text_name )
        if obj != obj2:
            print( 'Failed', obj, obj2 )
            return  1
        return  0

    if file_name:
        obj= load_object( file_name )
        if obj is None:
            print( 'load error:', file_name )
            return  1

        if output_name:
            save_object( output_name, obj )
    else:
        usage()
    return  0

if __name__=='__main__':
    sys.exit( main( sys.argv ) )


