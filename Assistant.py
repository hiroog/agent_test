# 2025/3/16 Hiroyuki Ogasawara
# vim:ts=4 sw=4 et:

import sys
import os
import json
import importlib

lib_path= os.path.dirname(__file__)
if lib_path not in sys.path:
    sys.path.append( lib_path )
import OllamaAPI4
import SlackAPI
import Functions
import TextLoader

#------------------------------------------------------------------------------

# config.json
# {
#    "base_url": "http://localhost:11434",
#    "preset-name1": {
#       "model": "model-name",          option
#       "system_prompt": "prompt",      option
#       "base_prompt": "prompt",        option
#       "num_ctx": 4096,                option
#       "temperature": 0.7,             option
#       "tools": [
#          "calculator",
#       ]
#    }
# }

# config.txt
# S base_url    http://localhost:11434
# S provider    provider                option
# S model       model-name              option
# I num_ctx     4096                    option
# F temperature 0.7                     option
# I top_k       20                      option
# F top_p       1.0                     option
# F min_p       0.0                     option
# F presence_penalty  0.0               option
# F frequency_penalty 1.0               option
# A env envname=envvalue ～             option
# A inline_mcp  FileTools Memory        option
# ======== preset-name1
# S base_url    http://localhost:11434  option
# S provider    provider                option
# S model       model-name              option
# I num_ctx     4096                    option
# F temperature 0.7                     option
# I top_k       20                      option
# F top_p       1.0                     option
# F min_p       0.0                     option
# A env envname=envvalue ～             option
# A tools       calculator              option
# ====T system_prompt                   option
# prompt
# ====T base_prompt                     option
# prompt
# ======== preset-name2
# A chain       preset-name1 preset-name2 ..
# ======== preset-name3
# S include_prompt prompt.md            option

# input_file.json
# {
#    "prompt": "～",
#    "system": "～",    option
#    "header": "～",    option
#    "model": "",       option
#    "preset": "",      option
#    "env": [           option
#       "envname=envvalue"
#    ]
# }

# input_file.txt
# S preset ～               option
# S model ～                option
# A env envname=envvalue ～ option
# ====T prompt
# ～
# ====T system          option
# ～
# ====T header          option
# ～


#------------------------------------------------------------------------------

class AssistantOptions(OllamaAPI4.OllamaOptions):
    def __init__( self, **args ):
        super().__init__()
        self.print= False
        self.input_file= None
        self.output_text= None
        self.channel= None
        self.config_file= 'config.txt'
        self.preset= 'default'
        self.nossl= False
        self.prompt_dir= '.'
        self.env= []
        self.base_prompt= None
        self.system_prompt= None
        self.header= ''
        self.tool_env= Functions.ToolEnv()
        self.apply_params( args )

    def copy_from( self, src ):
        super().copy_from( src )
        self.tool_env= Functions.ToolEnv( src.tool_env.to_dict() )
        return  self

    def set_env( self, env_list ):
        for name in env_list:
            params= name.split( '=', 1 )
            self.tool_env.set( params[0], params[1] )

#------------------------------------------------------------------------------

class Assistant:

    MERGE_KEY_LIST= [ 'base_url', 'provider', 'model', 'num_ctx', 'temperature', 'top_k', 'top_p', 'min_p', 'presence_penalty', 'frequency_penalty', 'env', 'base_prompt', 'system_prompt', 'header' ]

    def __init__( self, options ):
        self.config= self.load_file( options.config_file )
        options.tools= Functions.get_toolbox()
        options.tools.debug_echo= options.debug_echo
        self.options= options
        self.options.merge_params( self.config, self.MERGE_KEY_LIST )
        options.set_env( self.options.env )
        self.ollama_api= OllamaAPI4.OllamaAPI( options )
        self.import_inline_modules()

    #--------------------------------------------------------------------------

    def import_inline_modules( self ):
        for mcp_module in self.config.get( 'inline_mcp', [] ):
            importlib.import_module( mcp_module )

    #--------------------------------------------------------------------------
    def load_json( self, file_name ):
        if os.path.exists( file_name ):
            with open( file_name, 'r', encoding='utf-8' ) as fi:
                return  json.loads( fi.read() )
        return  None

    def load_file( self, file_name ):
        print( 'load:', file_name, flush=True )
        if file_name.lower().endswith( '.json' ):
            return  self.load_json( file_name )
        loader= TextLoader.TextLoader()
        return  loader.load( file_name )

    def load_prompt( self, file_name, base_prompt ):
        prompt_file= os.path.join( self.options.prompt_dir, file_name )
        if os.path.exists( prompt_file ):
            print( 'load:', prompt_file, flush=True )
            with open( prompt_file, 'r', encoding='utf-8' ) as fi:
                prompt= fi.read()
            if base_prompt:
                return  base_prompt + prompt
            return  prompt
        return  base_prompt

    def load_preset2( self, preset_name, load_prompt ):
        local_options= AssistantOptions().copy_from( self.options )
        if self.config:
            if preset_name in self.config:
                preset= self.config[preset_name]
                local_options.merge_params( preset, self.MERGE_KEY_LIST )
                if local_options.tools:
                    local_options.tool_info_list= local_options.tools.get_tools( preset.get('tools') )
                if load_prompt:
                    if 'include_system' in preset:
                        local_options.system_prompt= self.load_prompt( preset['include_system'], local_options.system_prompt )
                    if 'include_prompt' in preset:
                        local_options.base_prompt= self.load_prompt( preset['include_prompt'], local_options.base_prompt )
        return  local_options

    #--------------------------------------------------------------------------

    def generate_text( self, input_obj, preset_name= None, message_list= None ):
        if message_list is None:
            message_list= []
        if preset_name is None:
            preset_name= input_obj.get( 'preset', self.options.preset )
        prompt= input_obj['prompt']
        system= input_obj.get( 'system', None )
        is_root= message_list == []
        local_options= self.load_preset2( preset_name, is_root )
        if is_root:
            if local_options.base_prompt:
                prompt= local_options.base_prompt + '\n' + prompt
            if local_options.system_prompt:
                if system:
                    local_options.system_prompt+= '\n' + system
                system= local_options.system_prompt
        if 'model' in input_obj:
            local_options.model= input_obj['model']
        local_options.prompt= prompt
        local_options.set_env( local_options.env )
        if 'env' in input_obj:
            local_options.set_env( input_obj['env'] )
        header_text= input_obj.get( 'header', local_options.header )
        response,status_code= self.ollama_api.generate( prompt, system, None, message_list, local_options )
        if status_code != 200:
            print( 'Generate Error: %d' % status_code, flush=True )
            return  response,status_code,local_options
        if len(response) >= 1 and response[-1] != '\n':
            response+= '\n'
        response= header_text + response
        return  response,status_code,local_options

    def generate_chain( self, input_obj ):
        preset_name= input_obj.get( 'preset', self.options.preset )
        if self.config:
            if preset_name in self.config:
                preset= self.config[preset_name]
                if 'chain' in preset:
                    first_prompt= None
                    for chain_name in preset['chain']:
                        print( '>>>>> %s' % chain_name, flush=True )
                        response,status_code,local_options= self.generate_text( input_obj, chain_name )
                        if first_prompt is None:
                            first_prompt= local_options.prompt
                        if status_code != 200:
                            break
                        input_obj['prompt']= response
                    local_options.first_prompt= first_prompt
                    return  response,status_code,local_options
        response,status_code,local_options= self.generate_text( input_obj, preset_name )
        local_options.first_prompt= local_options.prompt
        return  response,status_code,local_options

    #--------------------------------------------------------------------------

    def stat_dump( self ):
        self.ollama_api.stat_dump()

    def f_post_or_save( self ):
        with OllamaAPI4.ExecTime( 'Assistant' ):
            if self.options.channel:
                token= os.environ.get( 'SLACK_API_TOKEN', None )
                if token is None:
                    print( 'SLACK_API_TOKEN must be set in the environment' ) 
                    return
            input_obj= None
            if self.options.input_file:
                input_obj= self.load_file( self.options.input_file )
                if input_obj is None:
                    print( 'Input file not found:', self.options.input_file )
                    return
            else:
                input_obj= { 'prompt':'' }
            response,status_code,local_options= self.generate_chain( input_obj )
            if status_code != 200:
                return
            if self.options.channel:
                api= SlackAPI.SlackAPI( token=token, nossl=self.options.nossl )
                channel_name= self.options.channel
                thread_ts= None
                if ':' in channel_name:
                    params= channel_name.split(':')
                    channel_name= params[0]
                    thread_ts= params[1]
                print( 'channel:', channel_name )
                print( 'thrad_ts:', thread_ts, flush=True )
                api.post_message(
                            channel_name,
                            text=response,
                            blocks= [
                                {
                                    'type': 'markdown',
                                    'text': response
                                }
                            ],
                            thread_ts=thread_ts
                        )
                api.save_cache()
            if self.options.output_text:
                with open( self.options.output_text, 'w', encoding='utf-8' ) as fo:
                    fo.write( response )
            if self.options.print:
                print( '** INPUT\n', local_options.first_prompt )
                print( '\n** RESPONSE\n', response, flush=True )
            if self.options.debug_echo:
                self.stat_dump()

    #--------------------------------------------------------------------------


#------------------------------------------------------------------------------

def usage():
    print( 'Assistant v1.34 Hiroyuki Ogasawara' )
    print( 'usage: Assistant [<options>] [<message..>]' )
    print( 'options:' )
    print( '  --preset <preset>' )
    print( '  --model <model_name>' )
    print( '  --host <server_url>         (default: http://localhost:11434)' )
    print( '  --provider <provider>' )
    print( '  --input <input.json|.txt>' )
    print( '  --num_ctx <num>' )
    print( '  --config <config.txt>' )
    print( '  --prompt_dir <prompt_dir>' )
    print( '  --save <output.txt>' )
    print( '  --post <channel>' )
    print( '  --timeout <sec>             (default: 600)' )
    print( '  --response_all' )
    print( '  --print' )
    print( '  --debug' )
    print( 'ex. python Assistant.py --input prompt.txt --print' )
    print( 'ex. python Assistant.py --preset assistant --print' )
    sys.exit( 1 )


def main( argv ):
    acount= len(argv)
    options= AssistantOptions()
    run_flag= False
    ai= 1
    while ai < acount:
        arg= argv[ai]
        if arg[0] == '-':
            if arg == '--model':
                ai= options.set_str( ai, argv, 'model' )
            elif arg == '--host':
                ai= options.set_str( ai, argv, 'base_url' )
            elif arg == '--provider':
                ai= options.set_str( ai, argv, 'provider' )
            elif arg == '--preset':
                ai= options.set_str( ai, argv, 'preset' )
            elif arg == '--input':
                ai= options.set_str( ai, argv, 'input_file' )
            elif arg == '--save':
                ai= options.set_str( ai, argv, 'output_text' )
                run_flag= True
            elif arg == '--post':
                ai= options.set_str( ai, argv, 'channel' )
                run_flag= True
            elif arg == '--config':
                ai= options.set_str( ai, argv, 'config_file' )
            elif arg == '--prompt_dir':
                ai= options.set_str( ai, argv, 'prompt_dir' )
            elif arg == '--num_ctx':
                ai= options.set_int( ai, argv, 'num_ctx' )
            elif arg == '--timeout':
                ai= options.set_int( ai, argv, 'timeout' )
            elif arg == '--response_all':
                ai= options.response_all= True
            elif arg == '--nossl':
                ai= options.nossl= True
            elif arg == '--print':
                options.print= True
                run_flag= True
            elif arg == '--debug':
                options.debug_echo= True
            else:
                print( 'Error: unknown option %s' % arg )
                usage()
        else:
            usage()
        ai+= 1

    if run_flag:
        api= Assistant( options )
        api.f_post_or_save()
    else:
        usage()

    return  0


if __name__=='__main__':
    sys.exit( main( sys.argv ) )


