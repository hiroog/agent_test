# 2025/3/16 Hiroyuki Ogasawara
# vim:ts=4 sw=4 et:

import sys
import os
import re
import json
import requests
import base64

#------------------------------------------------------------------------------

class OptionBase:
    def __init__( self ):
        pass

    def get_arg( self, ai, argv ):
        acount= len(argv)
        if ai+1 < acount:
            ai+= 1
            return  ai,argv[ai]
        return  ai,None

    def set_str( self, ai, argv, name ):
        ai,arg= self.get_arg( ai, argv )
        if arg:
            setattr( self, name, arg )
        return  ai

    def set_int( self, ai, argv, name ):
        ai,arg= self.get_arg( ai, argv )
        if arg:
            setattr( self, name, int(arg) )
        return  ai

    def set_float( self, ai, argv, name ):
        ai,arg= self.get_arg( ai, argv )
        if arg:
            setattr( self, name, float(arg) )
        return  ai

    def apply_params( self, params ):
        for key in params:
            setattr( self, key, params[key] )

class OllamaOptions(OptionBase):
    def __init__( self, **args ):
        super().__init__()
        self.base_url= os.environ.get('OLLAMA_HOST', 'http://localhost:11434' )
        self.provider= 'ollama2'
        self.system_role= 'system' # or developer
        self.timeout= 600
        self.model_name= 'qwen3:8b'
        self.num_ctx= 8192
        self.temperature= -1.0
        self.remove_think= True
        self.debug_echo= False
        self.tools= None
        self.apply_params( args )

def image_to_base64( image_data ):
    encoded_byte= base64.b64encode( image_data )
    return  encoded_byte.decode('utf-8')

def load_image( image_path ):
    with open( image_path, 'rb' ) as fi:
        return  fi.read()
    return  None

#------------------------------------------------------------------------------

class OllamaAPI:
    def __init__( self, options ):
        self.options= options

    #--------------------------------------------------------------------------

    def chat1_oai( self, text, system= None, image_data= None ):
        params= {
            'model': self.options.model_name,
            'messages': [
                {
                    "role": "user",
                    "content": text,
                }
            ],
        }
        if image_data:
            b64_image= image_to_base64( image_data )
            params['messages'][0]['content']= {
                {
                    "type": "input_text",
                    "text": text,
                },
                {
                    "type": "input_image",
                    "image": f"data:mage/jpeg:base64,{b64_image}",
                }
            }
        if system:
            params['messages'].insert( 0, { "role": self.options.system_role, "content": system } )
        api_url= self.options.base_url + '/v1/chat/completions'
        data= json.dumps( params )
        headers= {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer %s' % os.environ.get('OPENAI_API_KEY', 'lm-studio'),
        }
        try:
            result= requests.post( api_url, headers=headers, data=data, timeout=self.options.timeout )
        except Exception as e:
            return  '',408
        if result.status_code == 200:
            data= result.json()
            response= data['choices'][0]['message']['content']
            if self.options.remove_think:
                response= self.remove_think_tag( response )
            return  response,result.status_code
        else:
            print( 'Error: %d' % result.status_code, flush=True )
        return  '',result.status_code

    #--------------------------------------------------------------------------

    def generate_oai( self, text, system= None, image_data= None ):
        params= {
            'model': self.options.model_name,
            'input': text,
        }
        if image_data:
            b64_image= image_to_base64( image_data )
            params['input']= {
                {
                    "type": "input_text",
                    "text": text,
                },
                {
                    "type": "input_image",
                    "image": f"data:mage/jpeg:base64,{b64_image}",
                }
            }
        api_url= self.options.base_url + '/v1/response'
        data= json.dumps( params )
        headers= {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer %s' % os.environ.get('OPENAI_API_KEY', 'lm-studio'),
        }
        try:
            result= requests.post( api_url, headers=headers, data=data, timeout=self.options.timeout )
        except Exception as e:
            return  '',408
        if result.status_code == 200:
            data= result.json()
            response= data['output'][0]['content'][0]['text']
            if self.options.remove_think:
                response= self.remove_think_tag( response )
            return  response,result.status_code
        else:
            print( 'Error: %d' % result.status_code, flush=True )
        return  '',result.status_code

    #--------------------------------------------------------------------------

    def generate_ollama( self, text, system= None, image_data= None ):
        params= {
            'model': self.options.model_name,
            'prompt': text,
            'stream': False,
        }
        if system:
            params['system']= system
        if image_data:
            params['images']= [ image_to_base64( image_data ) ]
        api_url= self.options.base_url + '/api/generate'
        data= json.dumps( params )
        try:
            result= requests.post( api_url, headers={ 'Content-Type': 'application/json' }, data=data, timeout=self.options.timeout )
        except Exception as e:
            return  '',408
        if result.status_code == 200:
            data= result.json()
            response= data['response']
            if self.options.remove_think:
                response= self.remove_think_tag( response )
            return  response,result.status_code
        else:
            print( 'Error: %d' % result.status_code, flush=True )
        return  '',result.status_code

    #--------------------------------------------------------------------------

    def dump_object( self, ch, obj, ignore_set ):
        for key in obj:
            if key not in ignore_set:
                print( ' %s %s=%s' % (ch,key,obj[key]) )

    def dump_message( self, message ):
        role= message.get( 'role', '<UNKNOWN>' )
        content= message.get( 'content', '<None>' )
        print( '----- Role:[%s]' % role )
        print( content )
        ignore_set= set( ['role','content'] )
        self.dump_object( '*', message, ignore_set )

    def dump_response( self, response ):
        if 'message' in response:
            self.dump_message( response['message'] )
        ignore_set= set( ['message'] )
        self.dump_object( '+', response, ignore_set )

    def chat_ollama_1( self, message_list, tools ):
        if self.options.debug_echo:
            print( '============= SendMessages' )
            for message in message_list:
                self.dump_message( message )
            print( '=============', flush=True )
        params= {
            'model': self.options.model_name,
            'messages': message_list,
            'stream': False,
            'options': {
                'num_ctx': self.options.num_ctx,
            },
        }
        if self.options.temperature >= 0.0:
            params['options']['temperature']= self.options.temperature
        if tools:
            params['tools']= tools.get_tools()
        api_url= self.options.base_url + '/api/chat'
        data= json.dumps( params )
        if self.options.debug_echo:
            print( 'options=', params['options'], flush=True )
        try:
            result= requests.post( api_url, headers={ 'Content-Type': 'application/json' }, data=data, timeout=self.options.timeout )
        except Exception as e:
            return  None,408
        if result.status_code == 200:
            data= result.json()
            if self.options.debug_echo:
                print( '============= Response' )
                self.dump_response( data )
                print( '=============' )
            message= data['message']
            return  message,result.status_code
        else:
            print( 'Error: %d' % result.status_code, flush=True )
        return  None,result.status_code

    def generate_ollama_chat( self, text, system= None, image_data= None ):
        tools= self.options.tools
        message_list= []
        message= {
                    'role': 'user',
                    'content': text,
                }
        if image_data:
            message['images']= [ image_to_base64( image_data ) ]
        if system:
            message_list.append( {
                    'role': 'system',
                    'content': system,
                } )
        message_list.append( message )
        response= ''
        status_code= 408
        while True:
            message,status_code= self.chat_ollama_1( message_list, tools )
            if status_code != 200:
                return  '',status_code
            role= message['role']
            if role == 'assistant':
                if 'content' in message:
                    assistant_content= message['content']
                    message_list.append( message )
                tool_calls= message.get( 'tool_calls', None )
                if tool_calls:
                    for tool_call in tool_calls:
                        function= tool_call['function']
                        func_name= function['name']
                        arguments= function['arguments']
                        data= ''
                        if tools:
                            data= tools.call_func( func_name, arguments )
                        if self.options.debug_echo:
                            print( '**TOOL**', data, flush=True )
                        message= {
                                'role': 'tool',
                                'tool_name': func_name,
                                'content': data,
                            }
                        message_list.append( message )
                    continue
                response= message.get( 'content', '' )
                if self.options.remove_think:
                    response= self.remove_think_tag( response )
            break
        return  response,status_code

    #--------------------------------------------------------------------------

    def generate( self, text, system= None, image_data= None ):
        if self.options.provider == 'ollama':
            return  self.generate_ollama( text, system, image_data )
        elif self.options.provider == 'ollama2':
            return  self.generate_ollama_chat( text, system, image_data )
        elif self.options.provider == 'lmstudio':
            return  self.chat1_oai( text, system, image_data )
        elif self.options.provider == 'openai':
            return  self.generate_oai( text, system, image_data )
        return  '',400

    #--------------------------------------------------------------------------

    def remove_think_tag( self, response ):
        response= re.sub( r'\n*\<think\>.*?\<\/think\>\n*', '', response, flags=re.DOTALL )
        return  response

    #--------------------------------------------------------------------------


#------------------------------------------------------------------------------

def usage():
    print( 'OllamaAPI v4.10' )
    print( 'usage: OllamaAPI4 [<options>] [<message..>]' )
    print( 'options:' )
    print( '  --host <base_url>' )
    print( '  --model <model_name>' )
    print( '  --provider <provider>        # ollama2, openai, lmstudio' )
    print( '  --image <image_file>' )
    print( '  --input <text_file.txt>' )
    print( '  --output <save_file.txt>' )
    print( '  --num_ctx <num_ctx>          default 8192' )
    print( '  --temperature <temperature>' )
    print( '  --debug' )
    sys.exit( 0 )


def main( argv ):
    acount= len(argv)
    options= OllamaOptions( image_file= None )
    text_list= []
    ai= 1
    while ai < acount:
        arg= argv[ai]
        if arg[0] == '-':
            if arg == '--image':
                ai= options.set_str( ai, argv, 'image_file' )
            elif arg == '--model':
                ai= options.set_str( ai, argv, 'model_name' )
            elif arg == '--host':
                ai= options.set_str( ai, argv, 'base_url' )
            elif arg == '--provider':
                ai= options.set_str( ai, argv, 'provider' )
            elif arg == '--input':
                ai= options.set_str( ai, argv, 'input' )
            elif arg == '--output':
                ai= options.set_str( ai, argv, 'output' )
            elif arg == '--num_ctx':
                ai= options.set_int( ai, argv, 'num_ctx' )
            elif arg == '--temperature':
                ai= options.set_float( ai, argv, 'temperature' )
            elif arg == '--debug':
                options.debug_echo= True
            else:
                print( 'Error: unknown option %s' % arg )
                usage()
        else:
            text_list.append( arg )
        ai+= 1

    api= OllamaAPI( options )

    if options.input:
        with open( options.input, 'r', encoding='utf-8' ) as fi:
            text_list.append( fi.read() )
    if text_list != []:
        image_data= None
        if options.image_file:
            image_data= load_image( options.image_file )
            if image_data is None:
                print( 'Error: image file not found' )
                return  1
        input_text= ' '.join( text_list )
        print( 'prompt:', input_text )
        output_text,status_code= api.generate( input_text, image_data )
        print( 'output:', output_text )
        if options.output:
            with open( options.output, 'w', encoding='utf-8' ) as fo:
                fo.write( output_text )
    else:
        usage()
    return  0


if __name__=='__main__':
    sys.exit( main( sys.argv ) )


