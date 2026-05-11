# 2026/05/06 Hiroyuki Ogasawara
# vim:ts=4 sw=4 et:

import time
import boto3

#------------------------------------------------------------------------------

class BedrockAPI:
    def __init__( self, options, manager ):
        self.options= options
        self.manager= manager
        self.initialized= False

    #--------------------------------------------------------------------------

    def initialize( self ):
        if not self.initialized:
            self.client= boto3.client( 'bedrock-runtime', region_name=self.options.base_url )
            self.initialized= True

    #--------------------------------------------------------------------------

    def convert_tools( self, openai_tools ):
        bedrock_tools= []
        for openai_tool in openai_tools:
            openai_func= openai_tool['function']
            name= openai_func['name']
            print( f'Convert "{name}" OpenAI to Bedrock' )
            bedrock_func= {
                'name': openai_func['name'],
                'description': openai_func['description'],
                'inputSchema': {
                    'json': openai_func['parameters']
                }
            }
            bedrock_tools.append( {
                    'toolSpec': bedrock_func
                } )
        return  bedrock_tools

    def remove_empty_content( self, message ):
        result_list= []
        content_list= message.get('content',[])
        for content in content_list:
            if 'text' in content:
                text= content.get('text','')
                if text == '':
                    continue
            result_list.append( content )
        message['content']= result_list
        return  message

    def split_system( self, message_list ):
        result_list= []
        system_list= None
        for message in message_list:
            role= message.get('role')
            if role == 'system':
                system_list= message.get( 'content' )
            else:
                result_list.append( message )
        return  result_list,system_list


    def openai_to_bedrock( self, message_list ):
        bedrock_list= []
        system_message= None
        for openai_message in message_list:
            role= openai_message.get('role')
            if role == 'system':
                system_message= [ { 'text': openai_message.get('content','') } ]
                continue
            content= openai_message.get('content', '')
            bendrock_content_list= []
            if content != '':
                bendrock_content_list.append( { 'text': content } )
            for tool_call in openai_message.get('tool_calls',[]):
                pass
            bedrock_message= { 'role': role, 'content': bedrock_content_list }
            bedrock_list.append( bedrock_message )

    #--------------------------------------------------------------------------

    def chat_1( self, message_list, tools, options ):
        if options.debug_echo:
            self.dump_message_list( message_list )

        toolConfig= None
        openai_tools= None
        if options.tool_info_list != []:
            openai_tools= options.tool_info_list
        elif tools:
            openai_tools= tools.get_tools()
        if openai_tools:
            toolConfig= {
                    'tools': self.convert_tools( openai_tools )
                }

        inferenceConfig= {}
        additionalModelRequestFields= {}
        if options.temperature >= 0.0:
            inferenceConfig['temperature']= options.temperature
        if options.top_k > 0:
            additionalModelRequestFields['top_k']= options.top_k
        if options.top_p > 0.0:
            inferenceConfig['topP']= options.top_p
        if options.max_tokens > 0:
            inferenceConfig['maxTokens']= options.max_tokens
        if options.reasoning:
            if options.reasoning != 'off':
                tokens= { 'low': 1024, 'medium': 2048, 'high': 4096 }
                additionalModelRequestFields['thinking']= { 'type': 'enabled', 'budget_tokens': tokens.get(options.reasoning,2048) }
        if options.debug_echo:
            print( 'options=', inferenceConfig, additionalModelRequestFields, flush=True )

        message_list,system_list= self.split_system( message_list )

        try:
            params= {
                'modelId': options.model,
                'messages': message_list,
            }
            if system_list:
                params['system']= system_list
            if toolConfig:
                params['toolConfig']= toolConfig
            if inferenceConfig:
                params['inferenceConfig']= inferenceConfig
            if additionalModelRequestFields:
                params['additionalModelRequestFields']= additionalModelRequestFields

            start_time= time.perf_counter()
            result= self.client.converse( **params )
            request_time= time.perf_counter() - start_time
        except Exception as e:
            print( str(e), flush=True )
            return  '',408

        status_code= result.get('ResponseMetadata',{}).get('HTTPStatusCode',0)
        if status_code == 200:
            if options.debug_echo:
                self.dump_response( result )
            if 'usage' in result:
                usage= result['usage']
                if self.manager:
                    self.manager.stat_add( usage.get('outputTokens',0), usage.get('inputTokens',0), request_time )
            message= result.get('output',{}).get('message')
            return  message,status_code
        else:
            print( 'Error: %d' % status_code, flush=True )
        return  None,status_code

    def chat( self, text, system= None, image_data= None, message_list= None, options= None ):
        self.initialize()
        tools= options.tools
        if message_list is None:
            message_list= []
        message= {
                    'role': 'user',
                    'content': [
                            {
                                'text': text,
                            }
                        ]
                }
        system_list= None
        if system:
            message_list.append( {
                        'role': 'system',
                        'content': [ {
                            'text': system,
                        } ]
                    } )
        message_list.append( message )

        response= ''
        last_response= ''
        status_code= 408
        while True:
            message,status_code= self.chat_1( message_list, tools, options )
            if status_code != 200:
                return  response,status_code
            message_list.append( self.remove_empty_content(message) )
            role= message['role']
            if role == 'assistant':
                tool_calls= []
                if 'content' in message:
                    content_list= message['content']
                    for content in content_list:
                        if 'text' in content:
                            last_resonse= content['text']
                            if last_resonse.strip() != '':
                                response+= last_resonse + '\n'
                        elif 'toolUse' in content:
                            tool_calls.append( content['toolUse'] )

                if tool_calls != []:
                    if tools:
                        tool_result_list= []
                        for tool_call in tool_calls:
                            tool_call_id= tool_call['toolUseId']
                            func_name= tool_call['name']
                            arguments= tool_call['input']
                            data= ''
                            print( '**TOOLCALL**:', func_name, arguments, flush=True )
                            data= tools.call_func( func_name, arguments, options.tool_env )
                            tool_result_list.append(
                                    {
                                        'toolResult': {
                                            'toolUseId': tool_call_id,
                                            'content': [
                                                {
                                                    'text': data
                                                }
                                            ]
                                        }
                                    }
                                )
                            if options.response_all:
                                response+= '\U0001f527 toolcall: %s\n' % func_name
                        message= {
                            'role': 'user',
                            'content': tool_result_list
                        }
                        message_list.append( message )
                        continue
                if not options.response_all:
                    response= last_resonse
            break
        return  response,status_code

    #--------------------------------------------------------------------------

    def bedrock_to_openai( sefl, message ):
        role= message['role']
        if role != 'assistant':
            return  None
        openai_message= { 'role': 'assistant' }
        content_list= message.get( 'content', [] )
        tool_calls= []
        for content in content_list:
            if 'text' in content:
                text= content['text']
                openai_message['content']= text
            elif 'toolUse' in content:
                tool_use= content['toolUse']
                tool_call_id= tool_use['toolUseId']
                name= tool_use['name']
                arguments= tool_use['input']
                tool= {
                        'id': tool_call_id,
                        'type': 'function',
                        'function': {
                                'name': name,
                                'arguments': arguments,
                            }
                    }
                tool_calls.append( tool )
            elif 'reasoningContent' in content:
                text= content['reasoningContent']['reasoningText']['text']
                openai_message['reasoning']= text
            if tool_calls != []:
                openai_message['tool_calls']= tool_calls
        return  openai_message

    def openai_to_bedrock( sefl, openai_message_list ):
        bedrock_message_list= []
        bedrock_system= None
        prev_tools_result= None
        for message in openai_message_list:
            role= message.get('role')
            if role == 'tool':
                tool_call_id= message.get( 'tool_call_id', '' )
                func_name= message.get( 'name', '' )
                tool_content= message.get( 'content', '' )
                if not prev_tools_result:
                    prev_tools_result= []
                    bedrock_message_list.append( {
                            'role': 'user',
                            'content': prev_tools_result
                        } )
                prev_tools_result.append( {
                        'toolResult': {
                            'toolUseId': tool_call_id,
                            'content': [ {
                                    'text': tool_content
                                } ]
                        }
                    } )
                continue
            prev_tools_result= None
            if role == 'user':
                content= message.get( 'content', '\n\n' )
                bedrock_message_list.append( {
                        'role': 'user',
                        'content': [ {
                                'text': content
                            } ]
                    } )
                continue
            if role == 'assistant':
                content= message.get( 'content', '' )
                tool_calls= message.get( 'tool_calls' )
                reasoning= message.get( 'reasoning' )
                content_list= []
                if content != '':
                    content_list.append( {
                                'text': content
                            } )
                if reasoning:
                    content_list.append( {
                                'reasoningContent': {
                                        'reasoningText': {
                                                'text': reasoning
                                            }
                                    }
                            } )
                if tool_calls:
                    for tool_call in tool_calls:
                        tool_call_id= tool_call.get( 'id', '' )
                        function= tool_call['function' ]
                        func_name= function['name']
                        arguments= function['arguments']
                        content_list.append( {
                                'toolUse': {
                                        'toolUseId': tool_call_id,
                                        'name': func_name,
                                        'input': arguments,
                                    }
                            } )
                bedrock_message_list.append( {
                        'role': 'assistant',
                        'content': content_list
                    } )
                continue
            if role == 'system':
                content= message.get( 'content', '' )
                if content.strip() != '':
                    bedrock_system= [ {
                            'text': content
                        } ]
                continue
            print( 'Fatal error: Unknown role "%s"' % role, flush=True )
        return  bedrock_message_list,bedrock_system

    #--------------------------------------------------------------------------

    def chat2_1( self, session ):
        openai_message_list= session.get_messages()
        message_list,system_list= self.openai_to_bedrock( openai_message_list )

        options= session.get_options()
        if options.debug_echo:
            #self.manager.dump_message_list( 'SendMessages', openai_message_list )
            self.dump_message_list( message_list )

        toolConfig= None
        openai_tools= None
        if options.tool_info_list != []:
            openai_tools= options.tool_info_list
        if openai_tools:
            toolConfig= {
                    'tools': self.convert_tools( openai_tools )
                }

        inferenceConfig= {}
        additionalModelRequestFields= {}
        if options.temperature >= 0.0:
            inferenceConfig['temperature']= options.temperature
        if options.top_k > 0:
            additionalModelRequestFields['top_k']= options.top_k
        if options.top_p > 0.0:
            inferenceConfig['topP']= options.top_p
        if options.max_tokens > 0:
            inferenceConfig['maxTokens']= options.max_tokens
        if options.reasoning:
            if options.reasoning != 'off':
                tokens= { 'low': 1024, 'medium': 2048, 'high': 4096 }
                additionalModelRequestFields['thinking']= { 'type': 'enabled', 'budget_tokens': tokens.get(options.reasoning,2048) }
        if options.debug_echo:
            print( 'options=', inferenceConfig, additionalModelRequestFields, flush=True )

        try:
            params= {
                'modelId': options.model,
                'messages': message_list,
            }
            if system_list:
                params['system']= system_list
            if toolConfig:
                params['toolConfig']= toolConfig
            if inferenceConfig:
                params['inferenceConfig']= inferenceConfig
            if additionalModelRequestFields:
                params['additionalModelRequestFields']= additionalModelRequestFields

            start_time= time.perf_counter()
            result= self.client.converse( **params )
            request_time= time.perf_counter() - start_time
        except Exception as e:
            print( str(e), flush=True )
            return  '',408

        status_code= result.get('ResponseMetadata',{}).get('HTTPStatusCode',0)
        if status_code == 200:
            if options.debug_echo:
                self.dump_response( result )
            if 'usage' in result:
                usage= result['usage']
                if self.manager:
                    self.manager.stat_add( usage.get('outputTokens',0), usage.get('inputTokens',0), request_time )
            message= result.get('output',{}).get('message')
            return  message,status_code
        else:
            print( 'Error: %d' % status_code, flush=True )
        return  None,status_code

    def chat2( self, session ):
        options= session.get_options()
        toolbox= session.get_toolbox()
        self.initialize()
        session.fix_messages( True, 'reasoning' )

        response= ''
        content= ''

        status_code= 408
        while True:
            message,status_code= self.chat2_1( session )
            if status_code != 200:
                return  response,status_code

            role= message['role']
            if role != 'assistant':
                return  f'Unknown role "{role}" error',400

            message= self.bedrock_to_openai( message )

            content= message.get('content')
            tool_calls= message.get('tool_calls')
            reasoning= message.get('reasoning')
            session.push_assistant( content, tool_calls, reasoning, 'reasoning' )

            if content and content.strip() != '':
                response+= content + '\n'

            if tool_calls:
                toolresult= False
                for tool_call in tool_calls:
                    tool_call_id= tool_call['id']
                    function= tool_call['function']
                    func_name= function['name']
                    arguments= function['arguments']
                    data= ''
                    if toolbox:
                        print( '**TOOLCALL**:', func_name, arguments, flush=True )
                        data= toolbox.call_func( func_name, arguments, session.get_tool_env() )
                    session.push_result( data, func_name, tool_call_id )
                    toolresult= True
                    if options.response_all:
                        response+= '\U0001f527 toolcall: %s\n' % func_name
                if toolresult:
                    continue
            break

        if not options.response_all:
            response= content
        return  response,status_code

    #--------------------------------------------------------------------------

    def dump_object( self, ch, obj, ignore_set ):
        for key in obj:
            if key not in ignore_set:
                print( ' %s %s=%s' % (ch,key,obj[key]) )

    def dump_reasoning( self, message ):
        reasoning_text= message.get('reasoningContent')
        if reasoning_text:
            print( '<<<Thinking>>>' )
            print( reasoning_text )

    def dump_message( self, message ):
        role= message.get( 'role', '<UNKNOWN>' )
        content_list= message.get( 'content', [] )
        system_list= message.get( 'system', [] )
        print( '----- Role:[%s] -----' % role )
        for system in system_list:
            pass
        for content in content_list:
            if 'text' in content:
                print( '<<<Text>>>' )
                print( content['text'] )
            elif 'reasoningContent' in content:
                print( '<<<Thinking>>>' )
                text= content['reasoningContent']['reasoningText']['text']
                print( text )
            elif 'toolUse' in content:
                tool_use= content['toolUse']
                print( ' * 🛠️toolUse: "%s" (id:%s)' % (tool_use['name'],tool_use['toolUseId']), tool_use['input'] )
            elif 'toolResult' in content:
                tool_result= content['toolResult']
                tool_call_id= tool_result['toolUseId']
                for result in tool_result['content']:
                    name= ''
                    print( '<<<toolResult "%s" (id:%s) >>>' % (name,tool_call_id)  )
                    text= result['text']
                    print( text )
            else:
                print( content )
                print( '---' )
        ignore_set= set( ['role','content'] )
        self.dump_object( '*', message, ignore_set )

    def dump_response( self, response ):
        print( '================= Response =================' )
        if 'output' in response:
            output= response['output']
            self.dump_message( output['message'] )
        ignore_set= set( ['output'] )
        self.dump_object( '+', response, ignore_set )
        print( '============================================', flush=True )

    def dump_message_list( self, message_list ):
        print( '=============== SendMessages ===============' )
        for message in message_list:
            self.dump_message( message )
        print( '============================================', flush=True )

    #--------------------------------------------------------------------------

#------------------------------------------------------------------------------

def main():
    def calc_add( a: int, b: int ) -> int:
        """Add two numbers"""
        return  a + b
    import CommonAPI
    options= CommonAPI.CommonOptions(
                model='jp.amazon.nova-2-lite-v1:0',
                base_url= 'ap-northeast-1',
                debug_echo= True,
                print= True
            )
    session= CommonAPI.Session( None, options )
    session.get_toolbox().tool()( calc_add )
    session.set_tools( [ 'calc_add' ] )
    session.push_user( 'tool使って128348121+12734891+38298342計算して' )
    api= BedrockAPI( options, None )
    result,_= api.chat2( session )
    print( result )
    return  0

if __name__=='__main__':
    main()

