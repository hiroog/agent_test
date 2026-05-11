# 2025/3/16 Hiroyuki Ogasawara
# vim:ts=4 sw=4 et:

import sys
import os
import json
import time
import datetime

lib_path= os.path.dirname(__file__)
if lib_path not in sys.path:
    sys.path.append( lib_path )
import Functions

#------------------------------------------------------------------------------
# {
#    'role': 'system'
#    'content': 'text'
# },
# {
#    'role': 'user'
#    'content': 'text'
# },
# {
#    'role': 'assistant'
#    'content': 'text'
#    'reasoning': 'text'
#    'tool_calls': [ { 'id': 'id', 'function': { 'name':'name', 'arguments': argdict } } .. ]
# },
# {
#    'role': 'tool'
#    'content': 'text'
#    'name': 'func'
#    'tool_call_id': 'id'
# },

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

    def merge_params( self, params, key_list ):
        for key in key_list:
            if key in params:
                setattr( self, key, params[key] )

    def copy_from( self, src ):
        self.merge_params( src.__dict__, src.__dict__.keys() )
        return  self

#------------------------------------------------------------------------------

class ExecTime:
    def __init__( self, msg= None ):
        self.msg= ''
        if msg:
            self.msg= msg + ' '

    def get_time( self, sec ):
        if sec > 60*60:
            return  '%d:%02d:%05.2f' % (sec//(60*60), (sec//60)%60, sec - (sec//60)*60 )
        elif sec > 60:
            return  '%d:%05.2f' % (sec//60, sec - (sec//60)*60 )
        return  '%.2f' % sec

    def get_date( self ):
        day= datetime.datetime.today()
        return  '%04d/%02d/%02d %02d:%02d:%02d' % (day.year,day.month,day.day,day.hour,day.minute,day.second)

    def __enter__( self ):
        self.start_time= time.perf_counter()
        self.start_date= self.get_date()
        print( '\n%s Start [%s]\n' % (self.msg,self.start_date), flush=True )
        return  self

    def __exit__( self, *arg ):
        total_time= time.perf_counter() - self.start_time
        print( '\n%s%s (%.2f sec) [%s - %s]' % (self.msg, self.get_time( total_time ), total_time, self.start_date, self.get_date()), flush=True )
        return  False

#------------------------------------------------------------------------------

def save_json( file_name, message_obj ):
    if os.path.exists( file_name ):
        file_name_bak= file_name+'.bak'
        if os.path.exists( file_name_bak ):
            os.remove( file_name_bak )
        os.rename( file_name, file_name_bak )
    with open( file_name, 'w', encoding='utf-8' ) as fo:
        fo.write( json.dumps( message_obj, indent=4, ensure_ascii=False ) )

def load_json( file_name ):
    if os.path.exists( file_name ):
        with open( file_name, 'r', encoding='utf-8', errors='ignore' ) as fi:
            return  json.loads( fi.read() )
    return  None

#------------------------------------------------------------------------------

class Session:
    REASONING_TAGS= [ 'reasoning', 'reasoning_content', 'thinking' ]

    def __init__( self, session_id= None, options=None ):
        self.session_id= session_id
        self.message_list= []
        self.system= None
        self.options= options
        self.msg_info= {}
        self.toolbox= Functions.get_toolbox()
        self.tool_env= Functions.ToolEnv()
        self.lock= None

    def is_root( self ):
        return  self.message_list == []

    def get_id( self ):
        return  self.session_id

    def get_info( self ):
        return  self.msg_info

    def get_lock( self ):
        return  self.lock

    #--------------------------------------------------------------------------

    def get_options( self ):
        return  self.options

    def set_options( self, options ):
        self.options= options

    #--------------------------------------------------------------------------

    def get_toolbox( self ):
        return  self.toolbox

    def set_tools( self, tools ):
        self.options.tool_info_list= self.toolbox.get_tools( tools )

    #--------------------------------------------------------------------------

    def get_tool_env( self ):
        return  self.tool_env

    def set_env( self, env_list ):
        for name in env_list:
            params= name.split( '=', 1 )
            self.tool_env.set( params[0], params[1] )

    #--------------------------------------------------------------------------

    def set_system( self, text ):
        self.system= { 'role': 'system', 'content': text }

    def push_user( self, text ):
        self.message_list.append( { 'role': 'user', 'content': text } )

    def push_assistant( self, text, tool_calls, reasoning, reasoning_tag= None ):
        message= { 'role': 'assistant' }
        if reasoning is not None:
            message[reasoning_tag]= reasoning
        if text is not None:
            message['content']= text
        if tool_calls is not None:
            message['tool_calls']= tool_calls
        self.message_list.append( message )

    def push_result( self, text, name, tool_id ):
        message= {
                'role': 'tool',
                'name': name,
                'tool_call_id': tool_id,
                'content': text,
              }
        self.message_list.append( message )

    def get_messages( self ):
        message_list= []
        if self.system:
            message_list.append( self.system )
        message_list.extend( self.message_list )
        return  message_list

    #--------------------------------------------------------------------------

    def fix_messages( self, to_dict, reasoning_tag ):
        print( '$$$$$$$$$$$$$ FIX ARGS $$$$$$$$$$$$$' )
        prev_message= None
        prev_role= None
        for message in self.message_list:
            role= message['role']
            if role == 'assistant':
                if 'tool_calls' in message:
                    tool_calls= message['tool_calls']
                    for tool_call in tool_calls:
                        if 'type' not in tool_call:
                            tool_call['type']= 'function'
                            print( '  $$ INSERT FUNCTION-TYPE $$' )
                        func= tool_call['function']
                        arg= func['arguments']
                        if to_dict:
                            if type(arg) is str:
                                func['arguments']= json.loads( arg )
                                print( '  $$ CONVERT ARG to Dict $$' )
                        else:
                            if type(arg) is dict:
                                func['arguments']= json.dumps( arg )
                                print( '  $$ CONVERT ARG to Json $$' )
                if 'content' not in message:
                    message['content']= '\n\n'
                for tag in self.REASONING_TAGS:
                    if tag in message:
                        if tag != reasoning_tag:
                            print( '  $$ CONVERT TAG %s to %s $$' % (tag, reasoning_tag) )
                            message[reasoning_tag]= message[tag]
                            del message[tag]
            elif role == 'user':
                if prev_role == 'user':
                    print( '  $$ MERGE USER MESSAGE $$' )
                    prev_message['content']+= '\n' + message['content']
                    message['content']= ''
                    message['role']= None
                    continue
            prev_role= role
            prev_message= message
        fixed_message_list= []
        for message in self.message_list:
            if message['role'] is not None:
                fixed_message_list.append( message )
            else:
                print( '  $$ DELETE MESSAGE $$' )
        self.message_list= fixed_message_list

    #--------------------------------------------------------------------------

    def save_session( self, file_name ):
        save_json( file_name, {
                    'session_id': self.session_id,
                    'message_list': self.message_list,
                    'system': self.system,
                    'options': self.options.__dict__,
                    'msg_info': self.msg_info,
                    'tool_env': self.tool_env.to_dict(),
                } )

    def load_session( self, file_name ):
        obj= load_json( file_name )
        if obj:
            self.session_id= obj.get('session_id')
            self.message_list= obj.get('message_list',[])
            self.system= obj.get('system')
            self.options= None
            self.msg_info= obj.get('msg_info',{})
            self.tool_env= Functions.ToolEnv( obj.get('tool_env',{}) )

#------------------------------------------------------------------------------

class CommonOptions(OptionBase):
    def __init__( self, **args ):
        super().__init__()
        self.base_url= 'http://localhost:8080'
        self.provider= 'openai'    # or openai
        self.system_role= 'system' # or developer
        self.timeout= 600
        self.model= 'qwen3.5:9b'
        self.num_ctx= 16384
        self.max_tokens= 0
        self.temperature= -1.0
        self.top_k= 0
        self.top_p= 0.0
        self.min_p= -1.0
        self.presence_penalty= -9.0
        self.frequency_penalty= -9.0
        self.remove_think= False
        self.reasoning= None        # on, off, default, low, medium, high
        self.streaming= False
        self.response_all= False
        self.debug_echo= False
        self.verify= True
        self.tools= []
        self.tool_info_list= []
        #self.tool_env= os.environ
        self.apply_params( args )

#------------------------------------------------------------------------------

class CommonAPI:
    def __init__( self, options ):
        self.options= options
        self.api_map= {}
        self.stat_reset()
        if self.options.debug_echo:
            Functions.get_toolbox().debug_echo= True

    #--------------------------------------------------------------------------

    def load_api( self, provider, options ):
        if options.debug_echo:
            print( 'provider: %s, model: %s, host: %s' % (provider,options.model,options.base_url), flush=True )
        if provider == 'lmstudio':
            provider= 'openai'
        elif provider.startswith( 'ollama' ):
            provider= 'ollama'
        if provider in self.api_map:
            return  self.api_map[provider]
        api= None
        if provider == 'openai':
            import  OpenAIAPI
            api= OpenAIAPI.OpenAIAPI( options, self )
            self.api_map[provider]= api
        elif provider == 'ollama':
            import  OllamaAPI5
            api= OllamaAPI5.OllamaAPI( options, self )
            self.api_map[provider]= api
        elif provider == 'bedrock':
            import  BedrockAPI2
            api= BedrockAPI2.BedrockAPI( options, self )
            self.api_map[provider]= api
        return  api

    #--------------------------------------------------------------------------

    def stat_reset( self ):
        self.stat_list= []

    def stat_add( self, input_tokens, output_tokens, request_time ):
        self.stat_list.append( (input_tokens,output_tokens,request_time) )
        if self.options.debug_echo:
            print( '# input=%d  output=%d  %f token/s' % (input_tokens,output_tokens,output_tokens/request_time) )

    def stat_dump( self ):
        request_count= len(self.stat_list)
        total_input= 0
        total_output= 0
        max_input= 0
        max_output= 0
        total_sec= 0.0
        for itokens,otokens,rtime in self.stat_list:
            total_input+= itokens
            total_output+= otokens
            max_input= max(max_input,itokens)
            max_output= max(max_output,otokens)
            total_sec+= rtime
        print( '# request_count=%d' % request_count )
        if request_count != 0:
            print( '# total_input=%d  max_input=%d' % (total_input,max_input) )
            print( '# total_output=%d  max_output=%d' % (total_output,max_output) )
            print( '# total %f token/s' % (total_output/total_sec), flush=True )

    #--------------------------------------------------------------------------

    def generate( self, text, system= None, image_data= None, message_list= None, options= None ):
        if options is None:
            options= self.options
        api= self.load_api( options.provider, options )
        if api:
            return  api.chat( text, system, image_data, message_list, options )
        return  'Unknown provider: %s' % provider,400

    def generate2( self, session ):
        options= session.get_options()
        api= self.load_api( options.provider, options )
        if api:
            return  api.chat2( session )
        return  'Unknown provider: %s' % provider,400

    #--------------------------------------------------------------------------

    def dump_object( self, ch, obj, ignore_set ):
        has_key= False
        for key in obj:
            if key not in ignore_set:
                if not has_key:
                    has_key= True
                    print( '<<<Params>>>' )
                print( ' %s %s=%s' % (ch,key,obj[key]) )

    def dump_toolcalls( self, message ):
        if 'tool_calls' in message:
            print( '<<<ToolCalls>>>' )
            for tool_call in message['tool_calls']:
                tool_id= tool_call['id']
                func= tool_call['function']
                print( ' * 🛠️ToolCall: "%s" (id:%s)' % (func['name'],tool_id), func['arguments'] )

    def dump_toolresult( self, message ):
        role= message.get( 'role', '<UNKNOWN>' )
        if role == 'tool':
            name= message.get('name')
            if name is None:
                name= message.get('tool_name')
            content= message.get('content','<None>')
            tool_call_id= message.get('tool_call_id','')
            print( '<<ToolCallResult "%s" (id:%s)>>' % (name,tool_call_id) )
            print( content )

    def dump_reasoning( self, message ):
        reasoning_tag= 'reasoning_content'
        reasoning_text= message.get('reasoning_content')
        if not reasoning_text:
            reasoning_tag= 'reasoning'
            reasoning_text= message.get('reasoning')
        if not reasoning_text:
            reasoning_tag= 'thinking'
            reasoning_text= message.get('thinking')
        if reasoning_text:
            print( '<<<Thinking "%s">>>' % reasoning_tag )
            print( reasoning_text )

    def dump_content( self, message ):
        if 'content' in message:
            text= message.get('content', '')
            if text.strip() != '':
                print( '<<<Content>>>' )
                print( text )

    def dump_message( self, message ):
        role= message.get( 'role', '<UNKNOWN>' )
        content= message.get( 'content', '<None>' )
        print( '----- Role:[%s] -----' % role )
        if role == 'tool':
            self.dump_toolresult( message )
            ignore_set= set( ['role','content','name','tool_name','tool_call_id'] )
        else:
            self.dump_reasoning( message )
            self.dump_content( message )
            self.dump_toolcalls( message )
            ignore_set= set( ['role','content','tool_calls','reasoning_content','reasoning','thinking'] )
        self.dump_object( '*', message, ignore_set )

    def dump_response( self, response ):
        print( '=============== Response ===============' )
        if 'message' in response:
            self.dump_message( response['message'] )
        if 'choices' in response:
            self.dump_message( response['choices'][0]['message'] )
        ignore_set= set( ['message','choices'] )
        self.dump_object( '+', response, ignore_set )
        print( '==============================================', flush=True )

    def dump_message_list( self, title, message_list ):
        print( '=============== %s ===============' % title )
        for message in message_list:
            self.dump_message( message )
        print( '==============================================', flush=True )

    #--------------------------------------------------------------------------


#------------------------------------------------------------------------------

def usage():
    print( 'CommonAPI v5.00 Hiroyuki Ogasawara' )
    print( 'usage: CommonAPI [<options>] [<message..>]' )
    print( 'options:' )
    print( '  --host <base_url>' )
    print( '  --model <model_name>' )
    print( '  --provider <provider>        # openai, ollama, bedrock' )
    print( '  --image <image_file>' )
    print( '  --input <text_file.txt>' )
    print( '  --output <save_file.txt>' )
    print( '  --num_ctx <num_ctx>          default 8192' )
    print( '  --temperature <temperature>' )
    print( '  --debug' )
    sys.exit( 1 )


def main( argv ):
    acount= len(argv)
    options= CommonOptions( image_file= None, input=None, output=None )
    text_list= []
    ai= 1
    while ai < acount:
        arg= argv[ai]
        if arg[0] == '-':
            if arg == '--image':
                ai= options.set_str( ai, argv, 'image_file' )
            elif arg == '--model':
                ai= options.set_str( ai, argv, 'model' )
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

    api= CommonAPI( options )

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

