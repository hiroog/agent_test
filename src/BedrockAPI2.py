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

    #--------------------------------------------------------------------------

    def chat_1( self, message_list, tools, options ):
        if options.debug_echo:
            print( '============= SendMessages' )
            for message in message_list:
                self.dump_message( message )
            print( '=============', flush=True )

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
        if options.temperature >= 0.0:
            inferenceConfig['temperature']= options.temperature
        if options.top_p > 0.0:
            inferenceConfig['topP']= options.top_p
        if options.debug_echo:
            print( 'options=', inferenceConfig, flush=True )

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

            start_time= time.perf_counter()
            result= self.client.converse( **params )
            request_time= time.perf_counter() - start_time
        except Exception as e:
            print( str(e), flush=True )
            return  '',408

        status_code= result.get('ResponseMetadata',{}).get('HTTPStatusCode',0)
        if status_code == 200:
            if options.debug_echo:
                print( '============= Response' )
                self.dump_response( result )
                print( '=============' )
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

    def dump_object( self, ch, obj, ignore_set ):
        for key in obj:
            if key not in ignore_set:
                print( ' %s %s=%s' % (ch,key,obj[key]) )

    def dump_message( self, message ):
        role= message.get( 'role', '<UNKNOWN>' )
        content_list= message.get( 'content', [] )
        print( '----- Role:[%s]' % role )
        for content in content_list:
            if 'text' in content:
                print( content['text'] )
                print( '---' )
            else:
                print( content )
                print( '---' )
        ignore_set= set( ['role','content'] )
        self.dump_object( '*', message, ignore_set )

    def dump_response( self, response ):
        if 'message' in response:
            self.dump_message( response['message'] )
        ignore_set= set( ['message'] )
        self.dump_object( '+', response, ignore_set )

    #--------------------------------------------------------------------------

#------------------------------------------------------------------------------

def main():
    def calc_add( a: int, b: int ) -> int:
        """Add two numbers"""
        return  a + b
    import Functions
    from CommonAPI
    mcp= Functions.get_toolbox()
    mcp.tool()( calc_add )
    options= CommonAPI.CommonOptions(
                model='jp.amazon.nova-2-lite-v1:0',
                base_url= 'ap-northeast-1',
                debug_echo= True,
                print= True,
                tools= mcp,
                tool_info_list= mcp.get_tools( ['calc_add'] )
            )
    api= BedrockAPI( options, None )
    result,_= api.chat( 'tool使って128348121+12734891計算して', None, None, None, options )
    print( result )
    return  0

if __name__=='__main__':
    main()

