# 2025/3/16 Hiroyuki Ogasawara
# vim:ts=4 sw=4 et:

import sys
import os
import json

sys.path.append( os.path.dirname(__file__) )
import OllamaAPI4
import SlackAPI
import Functions

#------------------------------------------------------------------------------

# config.json
# {
#    "preset": {
#        "name1": {
#           "model": "model-name",          option
#           "system_prompt": "prompt",      option
#           "base_prompt": "prompt",        option
#           "num_ctx": 4096,                option
#           "temperature": 0.7,             option
#           "tools": [
#              "calculator",
#           ]
#        }
#    }
# }

# input_json.json
# {
#    "prompt": "～",
#    "system": "～",    option
#    "header": "～",    option
#    "model": "",       option
#    "env": {           option
#       "envname": "envvalue"
#    }
# }

#------------------------------------------------------------------------------

class Assistant:
    def __init__( self, options ):
        self.config= self.load_json( options.config_file )
        options.tools= Functions.get_tools()
        options.tools.debug_echo= options.debug_echo
        self.options= options
        self.ollama_api= OllamaAPI4.OllamaAPI( options )

    #--------------------------------------------------------------------------
    def load_json( self, file_name ):
        if os.path.exists( file_name ):
            print( 'load:', file_name )
            with open( file_name, 'r', encoding='utf-8' ) as fi:
                return  json.loads( fi.read() )
        return  None

    def load_preset( self, preset_name ):
        if self.config:
            preset_map= self.config['preset']
            self.options.base_url= self.config.get( 'base_url', self.options.base_url )
            if preset_name in preset_map:
                preset= preset_map[preset_name]
                self.options.model_name= preset.get( 'model', self.options.model_name )
                self.options.num_ctx= preset.get( 'num_ctx', self.options.num_ctx )
                self.options.temperature= preset.get( 'temperature', self.options.temperature )
                self.options.tools.select_tools( preset['tools'] )
                return  preset.get( 'base_prompt', None ),preset.get( 'system_prompt', None )
        return  None, None

    def set_env( self, env_map ):
        for name in env_map:
            os.environ[name]= env_map[name]

    #--------------------------------------------------------------------------

    def generate_from_file( self, input_file ):
        preset_prompt,preset_system= self.load_preset( self.options.preset )
        input_obj= self.load_json( input_file )
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
        header_text= input_obj.get( 'header', '' )
        response,status_code= self.ollama_api.generate( prompt, system )
        if status_code != 200:
            print( 'Generate Error: %d' % status_code, flush=True )
            return  response,status_code,prompt
        if len(response) >= 1 and response[-1] != '\n':
            response+= '\n'
        response= header_text + response
        return  response,status_code,prompt

    #--------------------------------------------------------------------------

    def f_post_or_save( self ):
        if self.options.channel:
            token= os.environ.get( 'SLACK_API_TOKEN', None )
            if token is None:
                print( 'SLACK_API_TOKEN must be set in the environment' ) 
                return
        response,status_code,prompt= self.generate_from_file( self.options.input_json )
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
    print( 'Assistant v1.00' )
    print( 'usage: Assistant [<options>] [<message..>]' )
    print( 'options:' )
    print( '  --preset <preset>' )
    print( '  --model <model_name>' )
    print( '  --host <ollama_host>        (default: http://localhost:11434)' )
    print( '  --provider <provider>' )
    print( '  --input_json <input.json>' )
    print( '  --num_ctx <num>' )
    print( '  --config <config.json>' )
    print( '  --save <output.txt>' )
    print( '  --post <channel>' )
    print( '  --print' )
    print( '  --debug' )
    print( 'ex. python Assistant.py --input_json prompt.json --print' )
    sys.exit( 1 )


def main( argv ):
    acount= len(argv)
    options= OllamaAPI4.OllamaOptions( print=False, input_json=None, output_text=None, channel=None, config_file='config.json', preset='default' )
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
            elif arg == '--input_json':
                ai= options.set_str( ai, argv, 'input_json' )
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

    if options.input_json and run_flag:
        api= Assistant( options )
        api.f_post_or_save()
    else:
        usage()

    return  0


if __name__=='__main__':
    sys.exit( main( sys.argv ) )


