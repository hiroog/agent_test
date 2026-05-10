# 2025/3/16 Hiroyuki Ogasawara
# vim:ts=4 sw=4 et:

import os
import json
import requests
import base64
import time

#------------------------------------------------------------------------------

def image_to_base64( image_data ):
    encoded_byte= base64.b64encode( image_data )
    return  encoded_byte.decode('utf-8')

def load_image( image_path ):
    with open( image_path, 'rb' ) as fi:
        return  fi.read()
    return  None

class OpenAIAPI:
    def __init__( self, options, manager ):
        self.options= options
        self.manager= manager

    #--------------------------------------------------------------------------

    def chat_1( self, message_list, tools, options ):
        if options.debug_echo:
            self.manager.dump_message_list( 'SendMessages', message_list )
        params= {
            'model': options.model,
            'messages': message_list,
        }
        if options.tool_info_list != []:
            params['tools']= options.tool_info_list
        elif tools:
            params['tools']= tools.get_tools()
        base_url= options.base_url
        if options.base_url[-1] == '/':
            base_url= base_url[:-1]
        if base_url.endswith( 'v1' ):
            api_url= base_url + '/chat/completions'
        else:
            api_url= base_url + '/v1/chat/completions'
        data= json.dumps( params )
        if options.temperature >= 0.0:
            params['temperature']= options.temperature
        if options.top_k > 0:
            params['top_k']= options.top_k
        if options.top_p > 0.0:
            params['top_p']= options.top_p
        if options.min_p >= 0.0:
            params['min_p']= options.min_p
        if options.presence_penalty >= -2.0:
            params['presence_penalty']= options.presence_penalty
        if options.frequency_penalty >= -2.0:
            params['frequency_penalty']= options.frequency_penalty
        if options.max_tokens > 0:
            params['max_tokens']= options.max_tokens
        if options.debug_echo:
            dump_params= {}
            for key in params:
                if key != 'messages' and key != 'tools':
                    dump_params[key]= params[key]
            print( 'options=', dump_params, flush=True )
        headers= {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer %s' % os.environ.get('OPENAI_API_KEY', 'lm-studio'),
        }
        try:
            start_time= time.perf_counter()
            result= requests.post( api_url, headers=headers, data=data, timeout=options.timeout, verify=options.verify )
            request_time= time.perf_counter() - start_time
        except Exception as e:
            print( 'err-url:',api_url )
            print( 'err-datasize:',len(data) )
            print( str(e), flush=True )
            return  '',408
        if result.status_code == 200:
            data= result.json()
            if options.debug_echo:
                self.manager.dump_response( data )
            if 'usage' in data:
                usage= data['usage']
                self.manager.stat_add( usage.get('completion_tokens',0), usage.get('prompt_tokens',0), request_time )
            if 'error' in data:
                return  { 'role': 'assistant', 'content': data['error'] },200
            message= data['choices'][0]['message']
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
            b64_image= image_to_base64( image_data )
            message['content']= {
                {
                    'type': 'input_text',
                    'text': text,
                },
                {
                    'type': 'input_image',
                    'image': f'data:mage/jpeg:base64,{b64_image}',
                }
            }
        if system:
            message_list.append( {
                    'role': options.system_role,
                    'content': system,
                } )
        message_list.append( message )
        response= ''
        status_code= 408
        while True:
            message,status_code= self.chat_1( message_list, tools, options )
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
                        arguments= json.loads(function['arguments'])
                        data= ''
                        if tools:
                            print( '**TOOLCALL**:', func_name, arguments, flush=True )
                            data= tools.call_func( func_name, arguments, options.tool_env )
                        message= {
                                'role': 'tool',
                                'name': func_name,
                                'tool_call_id': tool_call_id,
                                'content': data,
                            }
                        message_list.append( message )
                        if options.response_all:
                            response+= '\U0001f527 toolcall: %s\n' % func_name
                    continue
                if not options.response_all:
                    response= message.get( 'content', response )
            break
        return  response,status_code

    #--------------------------------------------------------------------------

    def chat2_1( self, session ):
        message_list= session.get_messages()
        options= session.get_options()
        if options.debug_echo:
            self.manager.dump_message_list( 'SendMessages', message_list )
        params= {
            'model': options.model,
            'messages': message_list,
        }
        if options.tool_info_list != []:
            params['tools']= options.tool_info_list
        data= json.dumps( params )
        if options.temperature >= 0.0:
            params['temperature']= options.temperature
        if options.top_k > 0:
            params['top_k']= options.top_k
        if options.top_p > 0.0:
            params['top_p']= options.top_p
        if options.min_p >= 0.0:
            params['min_p']= options.min_p
        if options.presence_penalty >= -2.0:
            params['presence_penalty']= options.presence_penalty
        if options.frequency_penalty >= -2.0:
            params['frequency_penalty']= options.frequency_penalty
        if options.max_tokens > 0:
            params['max_tokens']= options.max_tokens
        if options.debug_echo:
            dump_params= {}
            for key in params:
                if key != 'messages' and key != 'tools':
                    dump_params[key]= params[key]
            print( 'options=', dump_params, flush=True )
        base_url= options.base_url
        if options.base_url[-1] == '/':
            base_url= base_url[:-1]
        if base_url.endswith( 'v1' ):
            api_url= base_url + '/chat/completions'
        else:
            api_url= base_url + '/v1/chat/completions'
        headers= {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer %s' % os.environ.get('OPENAI_API_KEY', 'lm-studio'),
        }
        try:
            start_time= time.perf_counter()
            result= requests.post( api_url, headers=headers, data=data, timeout=options.timeout, verify=options.verify )
            request_time= time.perf_counter() - start_time
        except Exception as e:
            print( 'err-url:',api_url )
            print( 'err-datasize:',len(data) )
            print( str(e), flush=True )
            return  '',408
        if result.status_code == 200:
            data= result.json()
            if options.debug_echo:
                self.manager.dump_response( data )
            if 'usage' in data:
                usage= data['usage']
                self.manager.stat_add( usage.get('completion_tokens',0), usage.get('prompt_tokens',0), request_time )
            if 'error' in data:
                return  { 'role': 'assistant', 'content': data['error'] },200
            message= data['choices'][0]['message']
            return  message,result.status_code
        else:
            print( 'err-url:',api_url )
            print( 'err-datasize:',len(data) )
            print( 'err-data:', data )
            print( 'Error: %d' % result.status_code, flush=True )
        return  None,result.status_code

    def chat2( self, session ):
        options= session.get_options()
        toolbox= session.get_toolbox()
        session.fix_messages( False, 'reasoning' ) # dict to json
        response= ''
        content= ''
        status_code= 408
        while True:
            message,status_code= self.chat2_1( session )
            if status_code != 200:
                return  '',status_code
            role= message['role']
            if role != 'assistant':
                return  f'Unknown role "{role}" error',400
            content= message.get('content')
            tool_calls= message.get('tool_calls')
            reasoning= None
            reasoning_tag= 'reasoning'
            for tag in [ 'reasoning', 'reasoning_content', 'thinking' ]:
                if tag in message:
                    reasoning= message[tag]
                    reasoning_tag= tag
                    break
            session.push_assistant( content, tool_calls, reasoning, reasoning_tag )
            if content and content.strip() != '':
                response+= content + '\n'
            if tool_calls:
                for tool_call in tool_calls:
                    tool_call_id= tool_call['id']
                    function= tool_call['function']
                    func_name= function['name']
                    arguments= json.loads(function['arguments'])
                    data= ''
                    if toolbox:
                        print( '**TOOLCALL**:', func_name, arguments, flush=True )
                        data= toolbox.call_func( func_name, arguments, session.get_tool_env() )
                    session.push_result( data, func_name, tool_call_id )
                    if options.response_all:
                        response+= '\U0001f527 toolcall: %s\n' % func_name
                continue
            break
        if not options.response_all:
            response= content
        return  response,status_code

    #--------------------------------------------------------------------------

    def generate( self, text, system= None, image_data= None ):
        params= {
            'model': self.options.model,
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
            result= requests.post( api_url, headers=headers, data=data, timeout=self.options.timeout, verify=self.options.verify )
        except Exception as e:
            return  '',408
        if result.status_code == 200:
            data= result.json()
            response= data['output'][0]['content'][0]['text']
            return  response,result.status_code
        else:
            print( 'Error: %d' % result.status_code, flush=True )
        return  '',result.status_code

    #--------------------------------------------------------------------------


#------------------------------------------------------------------------------

