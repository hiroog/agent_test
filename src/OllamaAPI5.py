# 2025/3/16 Hiroyuki Ogasawara
# vim:ts=4 sw=4 et:

import sys
import os
import re
import json
import requests
import base64
import time
import datetime

#------------------------------------------------------------------------------

def image_to_base64( image_data ):
    encoded_byte= base64.b64encode( image_data )
    return  encoded_byte.decode('utf-8')

def load_image( image_path ):
    with open( image_path, 'rb' ) as fi:
        return  fi.read()
    return  None

#------------------------------------------------------------------------------

class OllamaAPI:
    def __init__( self, options, manager ):
        self.options= options
        self.manager= manager

    #--------------------------------------------------------------------------

    def decode_streaming( self, result ):
        content= ''
        thinking= ''
        tools= []
        for line in result.text.split( '\n' ):
            data= json.loads( line )
            message= data['message']
            role= message['role']
            content+= message['content']
            if 'thinking' in message:
                thinking+= message['thinking']
            if 'tool_calls' in message:
                tools.extend( message['tool_calls'] )
            if data['done']:
                break
        message['content']= content
        if thinking != '':
            message['thinking']= thinking
        if message['role'] == '':
            message['role']= 'assistant'
        if tools != []:
            message['tool_calls']= tools
        return  data

    #--------------------------------------------------------------------------

    def chat_1( self, message_list, tools, streaming= False, options= None ):
        if options.debug_echo:
            self.manager.dump_message_list( 'SendMessages', message_list )
        params= {
            'model': options.model,
            'messages': message_list,
            'stream': streaming,
            'options': {
                'num_ctx': options.num_ctx,
            },
        }
        if options.temperature >= 0.0:
            params['options']['temperature']= options.temperature
        if options.top_k > 0:
            params['options']['top_k']= options.top_k
        if options.top_p > 0.0:
            params['options']['top_p']= options.top_p
        if options.min_p >= 0.0:
            params['options']['min_p']= options.min_p
        if options.max_tokens > 0:
            params['options']['num_predict']= options.max_tokens
        if options.tool_info_list != []:
            params['tools']= options.tool_info_list
        elif tools:
            params['tools']= tools.get_tools()
        api_url= options.base_url + '/api/chat'
        data= json.dumps( params )
        if options.debug_echo:
            print( 'options=', params['options'], flush=True )
        headers= {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer %s' % os.environ.get('OLLAMA_API_KEY', os.environ.get( 'OPENAI_API_KEY', None) ),
        }
        try:
            start_time= time.perf_counter()
            result= requests.post( api_url, headers=headers, data=data, timeout=options.timeout, verify=options.verify )
            request_time= time.perf_counter() - start_time
        except Exception as e:
            print( 'err-url:',api_url )
            print( 'err-datasize:',len(data) )
            print( str(e), flush=True )
            return  None,408
        if result.status_code == 200:
            if streaming:
                data= self.decode_streaming( result )
            else:
                data= result.json()
            if options.debug_echo:
                self.manager.dump_response( data )
            self.manager.stat_add( data.get('eval_count',0), data.get('prompt_eval_count',0), request_time )
            message= data['message']
            return  message,result.status_code
        else:
            print( 'err-url:',api_url )
            print( 'err-datasize:',len(data) )
            print( 'Error: %d' % result.status_code, flush=True )
        return  None,result.status_code

    def chat( self, text, system= None, image_data= None, message_list= None, options= None ):
        tools= options.tools
        if message_list is None:
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
            message,status_code= self.chat_1( message_list, tools, False, options )
            if status_code != 200:
                return  '',status_code
            message_list.append( message )
            role= message['role']
            if role == 'assistant':
                if 'content' in message:
                    content= message['content']
                    if content.strip() != '':
                        response+= content + '\n'
                tool_calls= message.get( 'tool_calls', None )
                if tool_calls:
                    for tool_call in tool_calls:
                        tool_call_id= tool_call['id']
                        function= tool_call['function']
                        func_name= function['name']
                        arguments= function['arguments']
                        data= ''
                        if tools:
                            print( '**TOOLCALL**:', func_name, arguments, flush=True )
                            data= tools.call_func( func_name, arguments, options.tool_env )
                        message= {
                                'role': 'tool',
                                'tool_name': func_name,
                                'tool_call_id': tool_call_id,
                                'content': data,
                            }
                        message_list.append( message )
                        if options.response_all:
                            response+= '\U0001f527 toolcall: %s\n' % func_name
                    continue
                if not options.response_all:
                    response= message.get( 'content', response )
                if options.remove_think:
                    response= self.remove_think_tag( response )
            break
        return  response,status_code

    #--------------------------------------------------------------------------

    def generate( self, text, system= None, image_data= None ):
        params= {
            'model': self.options.model,
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
            result= requests.post( api_url, headers={ 'Content-Type': 'application/json' }, data=data, timeout=self.options.timeout, verify=self.options.verify )
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

    def remove_think_tag( self, response ):
        response= re.sub( r'\n*\<think\>.*?\<\/think\>\n*', '', response, flags=re.DOTALL )
        return  response

    #--------------------------------------------------------------------------


#------------------------------------------------------------------------------
