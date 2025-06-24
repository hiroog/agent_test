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

# input_json.json
# {
#    "prompt": "～",
#    "system": "～",
#    "header": "～",
#    "model": ""
# }

#------------------------------------------------------------------------------

class Assistant:
    def __init__( self, options ):
        options.tools= Functions.get_tools()
        self.options= options
        self.ollama_api= OllamaAPI4.OllamaAPI( options )

    #--------------------------------------------------------------------------

    def generate_from_file( self, input_file ):
        print( 'load:', input_file )
        with open( input_file, 'r', encoding='utf-8' ) as fi:
            input_obj= json.loads( fi.read() )
        prompt= input_obj['prompt']
        if 'system' in input_obj:
            prompt= input_obj['system'] + '\n' + prompt
        if 'model' in input_obj:
            self.options.model_name= input_obj['model']
        header_text= input_obj.get( 'header', '' )
        response,status_code= self.ollama_api.generate( prompt )
        if status_code != 200:
            print( 'Generate Error: %d' % status_code, flush=True )
            return  response,status_code
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
    print( '  --model <model_name>' )
    print( '  --host <ollama_host>        (default: http://localhost:11434)' )
    print( '  --provider <provider>       (default: ollama2)' )
    print( '  --input_json <input.json>' )
    print( '  --save <output.txt>' )
    print( '  --post <channel>' )
    print( '  --print' )
    print( '  --debug' )
    sys.exit( 0 )


def main( argv ):
    acount= len(argv)
    options= OllamaAPI4.OllamaOptions( print=False, input_json=None, output_text=None, channel=None )
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
            elif arg == '--input_json':
                ai= options.set_str( ai, argv, 'input_json' )
            elif arg == '--save':
                ai= options.set_str( ai, argv, 'output_text' )
                run_flag= True
            elif arg == '--post':
                ai= options.set_str( ai, argv, 'channel' )
                run_flag= True
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


