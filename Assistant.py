# 2025/3/16 Hiroyuki Ogasawara
# vim:ts=4 sw=4 et:

import sys
import os
import json

sys.path.append( os.path.dirname(__file__) )
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
# ======== preset-name1
# S model       model-name              option
# I num_ctx     4096                    option
# F temperature 0.7                     option
# A tools       calculator              option
# S base_url    http://localhost:11434
# ====T system_prompt                   option
# prompt
# ====T base_prompt                     option
# prompt
# ======== preset-name2
# A chain       preset-name1 preset-name2 ..

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

class Assistant:
    def __init__( self, options ):
        self.config= self.load_file( options.config_file )
        options.tools= Functions.get_tools()
        options.tools.debug_echo= options.debug_echo
        self.options= options
        self.ollama_api= OllamaAPI4.OllamaAPI( options )

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

    def load_preset( self, preset_name ):
        if self.config:
            self.options.base_url= self.config.get( 'base_url', self.options.base_url )
            self.options.model_name= self.config.get( 'model_name', self.options.model_name )
            self.options.num_ctx= self.config.get( 'num_ctx', self.options.num_ctx )
            self.options.temperature= self.config.get( 'temperature', self.options.temperature )
            self.options.top_k= self.config.get( 'top_k', self.options.top_k )
            self.options.top_p= self.config.get( 'top_p', self.options.top_p )
            self.options.min_p= self.config.get( 'min_p', self.options.min_p )
            if preset_name in self.config:
                preset= self.config[preset_name]
                self.options.base_url= preset.get( 'base_url', self.options.base_url )
                self.options.model_name= preset.get( 'model', self.options.model_name )
                self.options.num_ctx= preset.get( 'num_ctx', self.options.num_ctx )
                self.options.temperature= preset.get( 'temperature', self.options.temperature )
                self.options.top_k= preset.get( 'top_k', self.options.top_k )
                self.options.top_p= preset.get( 'top_p', self.options.top_p )
                self.options.min_p= preset.get( 'min_p', self.options.min_p )
                self.options.tools.select_tools( preset['tools'] )
                return  preset.get( 'base_prompt', None ),preset.get( 'system_prompt', None ),preset.get( 'header', '' )
        return  None,None,''

    def set_env( self, env_list ):
        for name in env_list:
            params= name.split( '=' )
            os.environ[params[0]]= params[1]

    #--------------------------------------------------------------------------

    def generate_text( self, input_obj, preset_name= None ):
        if preset_name is None:
            preset_name= input_obj.get( 'preset', self.options.preset )
        preset_prompt,preset_system,preset_header= self.load_preset( preset_name )
        prompt= input_obj['prompt']
        if preset_prompt:
            prompt= preset_prompt + '\n' + prompt
        system= input_obj.get( 'system', None )
        if preset_system and system:
            system+= preset_system + '\n' + system
        if 'model' in input_obj:
            self.options.model_name= input_obj['model']
        if 'env' in input_obj:
            self.set_env( input_obj['env'] )
        header_text= input_obj.get( 'header', preset_header )
        response,status_code= self.ollama_api.generate( prompt, system )
        if status_code != 200:
            print( 'Generate Error: %d' % status_code, flush=True )
            return  response,status_code,prompt
        if len(response) >= 1 and response[-1] != '\n':
            response+= '\n'
        response= header_text + response
        return  response,status_code,prompt

    def generate_chain( self, input_obj ):
        preset_name= input_obj.get( 'preset', self.options.preset )
        if self.config:
            if preset_name in self.config:
                preset= self.config[preset_name]
                if 'chain' in preset:
                    first_prompt= None
                    for chain_name in preset['chain']:
                        print( '>>>>> %s' % chain_name, flush=True )
                        response,status_code,prompt= self.generate_text( input_obj, chain_name )
                        if first_prompt is None:
                            first_prompt= prompt
                        if status_code != 200:
                            break
                        input_obj['prompt']= response
                    return  response,status_code,first_prompt
        return  self.generate_text( input_obj, preset_name )

    #--------------------------------------------------------------------------

    def f_post_or_save( self ):
        if self.options.channel:
            token= os.environ.get( 'SLACK_API_TOKEN', None )
            if token is None:
                print( 'SLACK_API_TOKEN must be set in the environment' ) 
                return
        input_obj= None
        if self.options.input_file:
            input_obj= self.load_file( self.options.input_file )
        else:
            print( 'Input file not found:', self.options.input_file )
            return
        response,status_code,prompt= self.generate_chain( input_obj )
        if status_code != 200:
            return
        if self.options.channel:
            api= SlackAPI.SlackAPI( token=token )
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
                        text=None,
                        markdown_text=response,
                        thread_ts=thread_ts
                    )
        if self.options.output_text:
            with open( self.options.output_text, 'w', encoding='utf-8' ) as fo:
                fo.write( response )
        if self.options.print:
            print( '** INPUT\n', prompt )
            print( '\n** RESPONSE\n', response, flush=True )

    #--------------------------------------------------------------------------


#------------------------------------------------------------------------------

def usage():
    print( 'Assistant v1.22' )
    print( 'usage: Assistant [<options>] [<message..>]' )
    print( 'options:' )
    print( '  --preset <preset>' )
    print( '  --model <model_name>' )
    print( '  --host <ollama_host>        (default: http://localhost:11434)' )
    print( '  --provider <provider>' )
    print( '  --input <input.json|.txt>' )
    print( '  --num_ctx <num>' )
    print( '  --config <config.txt>' )
    print( '  --save <output.txt>' )
    print( '  --post <channel>' )
    print( '  --timeout <sec>             (default: 600)' )
    print( '  --print' )
    print( '  --debug' )
    print( 'ex. python Assistant.py --input prompt.json --print' )
    sys.exit( 1 )


def main( argv ):
    acount= len(argv)
    options= OllamaAPI4.OllamaOptions( print=False, input_file=None, output_text=None, channel=None, config_file='config.txt', preset='default' )
    text_list= []
    run_flag= False
    ai= 1
    while ai < acount:
        arg= argv[ai]
        if arg[0] == '-':
            if arg == '--model':
                ai= options.set_str( ai, argv, 'model_name' )
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
            elif arg == '--num_ctx':
                ai= options.set_int( ai, argv, 'num_ctx' )
            elif arg == '--timeout':
                ai= options.set_int( ai, argv, 'timeout' )
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


