# 2025/08/16 Hiroyuki Ogasawara
# vim:ts=4 sw=4 et:

import sys
import os
import json

lib_path= os.path.dirname(__file__)
if lib_path not in sys.path:
    sys.path.append( lib_path )
import Assistant
import FileListLib
import Functions
import TextLoader
import SlackAPI
from OllamaAPI4 import OptionBase, ExecTime

#------------------------------------------------------------------------------

class AnalyzerOption(OptionBase):
    def __init__( self, **args ):
        super().__init__()
        self.root= '.'
        self.project= None
        self.engine= None
        self.list_file= 'list.txt'
        self.log_dir= 'logs'
        self.preset= 'cppreview'
        self.config_file= None
        self.prompt_dir= '.'
        self.debug= False
        self.limit= 0
        #---------------------------
        self.cache_file= 'slack_cache.json'
        self.channel= None
        self.nossl= False
        self.alias_file= None
        self.use_mention= False
        #---------------------------
        self.apply_params( args )

#------------------------------------------------------------------------------

class IssueList:
    def __init__( self ):
        self.issue_id= 0
        self.logs= []
    def append( self, title, file_name, description ):
        self.issue_id+= 1
        self.logs.append( (self.issue_id,title,file_name,description) )
        return  self.issue_id

issue_list= IssueList()

@Functions.tool.add
def create_issue( title:str, description:str, file_name:str ) -> str:
    """Add a new issue to the bug tracking system.

    Args:
        title: Issue title
        description: Issue description. Please include identifiable information such as file names and line numbers in the description along with the details of the issue.
        file_name: Filename
    """
    global issue_list
    issue_id= issue_list.append( title, file_name, description )
    print( 'New Issue: %s (%s)' % (title,file_name) )
    print( '  desc: %s' % title, flush=True )
    return  'Issue created : "%s" id=%d' % (title,issue_id)

#------------------------------------------------------------------------------

class CodeAnalyzer:
    def __init__( self, options ):
        self.options= options
        self.file_list= None
        self.file_map= {}
        self.uemode= options.project is not None
        options= Assistant.AssistantOptions( prompt_dir=options.prompt_dir, config_file=options.config_file )
        if self.options.debug:
            options.print= True
            options.debug_echo= True
        self.assistant= Assistant.Assistant( options )
        self.stat_analyzed_files= []
        self.stat_issue_files= []
        self.stat_total_issues= 0
        self.stat_analyze_time= ExecTime().get_date()

    #--------------------------------------------------------------------------

    def save_list( self, save_name, file_list ):
        print( 'save:', save_name )
        with open( save_name, 'w', encoding='utf-8' ) as fo:
            for file_name in file_list:
                fo.write( '%s\n' % file_name )
            fo.write( '# %d\n' % len(file_list) )

    def load_list( self, load_name ):
        print( 'load:', load_name )
        file_list= []
        with open( load_name, 'r', encoding='utf-8' ) as fi:
            for line in fi:
                line= line.strip()
                if line == '' or line[0] == '#':
                    continue
                file_list.append( line )
        return  file_list,{}

    # [
    #   {
    #     "name": "file_name",
    #     "users": [ "user1", "user2",.. ],
    #     "date": "date-time",
    #     "rev": "revision"
    #   },
    #   ...
    # ]
    def load_json( self, load_name ):
        print( 'load:', load_name )
        with open( load_name, 'r', encoding='utf-8' ) as fi:
            json_obj= json.loads( fi.read() )
        file_list= []
        file_map= {}
        for entry in json_obj:
            file_name= entry.get('name','')
            file_list.append( file_name )
            file_map[file_name]= entry
        return  file_list,file_map

    def save_json( self, save_name, obj ):
        with open( save_name, 'w', encoding='utf-8' ) as fo:
            fo.write( json.dumps( obj, indent=4 ) )

    #--------------------------------------------------------------------------

    def get_file_list( self, root ):
        file_list= FileListLib.FileListLib( '.code_analyzer_ignore' )
        file_list= file_list.find_file( root )
        ext_set_h= set( ['.h', '.hpp', '.inl'] )
        ext_set_c= set( ['.c', '.cpp'] )
        file_list2= []
        for file_name in file_list:
            _,ext= os.path.splitext( file_name )
            if ext in ext_set_h:
                file_list2.append( file_name )
            elif ext in ext_set_c:
                if self.uemode:
                    if file_name.endswith( '.gen.cpp' ):
                        continue
                    if '/Intermediate/' in file_name:
                        continue
                file_list2.append( file_name )
        return  file_list2

    #--------------------------------------------------------------------------

    def get_file_info( self, file_name ):
        if file_name == '':
            return  None
        if file_name in self.file_map:
            return  self.file_map[file_name]
        base_name= os.path.basename(file_name)
        for key in self.file_map:
            if base_name == os.path.basename(key):
                return  self.file_map[key]
        return  None

    def set_file_info( self, dest_obj, file_name, user_list ):
        file_info= self.get_file_info( file_name )
        if file_info:
            if 'date' in file_info:
                dest_obj['date']= file_info['date']
            if 'rev' in file_info:
                dest_obj['rev']= file_info['rev']
            if 'users' in file_info:
                user_list.extend( file_info['users'] )

    # ====== default
    # S file_name SOURCE
    # A sources SOURCE1 SOURCE2
    # I issue_count 1
    # S date 2025/03/30
    # S rev CL-0000
    # S users username
    # ====T response
    # ～
    # ====== issue_1
    # S file_name SOURCE
    # S date DATE
    # S rev REV
    # ====T title
    # ～
    # ====T description
    # ～

    def save_logs( self, response, prompt, file_list, issue_list ):
        log_obj= {}
        issue_count= len(issue_list.logs)
        default_obj= {
            'response': response,
            'file_name': file_list[0],
            'sources': file_list,
            'issue_count': issue_count,
        }
        user_list= []
        self.set_file_info( default_obj, file_list[0], user_list )
        log_obj['default']= default_obj

        if issue_count != 0:
            self.stat_issue_files.append( file_list[0] )
            self.stat_total_issues+= issue_count

        for issue in issue_list.logs:
            issue_id= issue[0]
            issue_name= 'issue_%d' % issue_id
            file_name= issue[2]
            issue_obj= {
                'issue_id': issue_id,
                'title': issue[1],
                'file_name': file_name,
                'description': issue[3],
            }
            self.set_file_info( issue_obj, file_name, user_list )
            log_obj[issue_name]= issue_obj

        log_obj['default']['users']= list( set(user_list) )

        log_dir= self.options.log_dir
        if not os.path.exists( log_dir ):
            os.makedirs( log_dir )
        output_file= '%s/%s.txt' % (log_dir, os.path.basename(file_list[0]) )
        TextLoader.TextLoader().save( output_file, log_obj )

    def analyze_1( self, file_list ):
        prompt_text= ''
        for file_name in file_list:
            prompt_text+= '- %s\n' % os.path.basename(file_name)
        env_array= []
        if self.options.project:
            env_array.append( 'MCP_PROJECT_ROOT=%s' % self.options.project )
            if self.options.engine:
                env_array.append( 'MCP_ENGINE_ROOT=%s' % self.options.engine )
        else:
            env_array.append( 'MCP_SOURCE_ROOT=%s' % self.options.root )
        input_obj= {
            'preset': self.options.preset,
            'prompt': prompt_text,
            'env': env_array,
        }
        if self.options.debug:
            print( 'input:', input_obj )

        global issue_list
        issue_list= IssueList()

        with ExecTime( 'Generate' ):
            response,status_code,prompt= self.assistant.generate_chain( input_obj )

        if status_code != 200:
            return  False

        self.save_logs( response, prompt, file_list, issue_list )
        return  True

    def analyze( self, file_list ):
        with ExecTime( 'Analyze' ):
            file_set= set(file_list)
            for file_name in file_list:
                base,ext= os.path.splitext( file_name )
                if ext == '.cpp':
                    analyze_list= [ file_name ]
                    header_file= base + '.h'
                    if header_file in file_set:
                        analyze_list.append( header_file )
                    if not self.analyze_1( analyze_list ):
                        break
                    self.stat_analyzed_files.append( file_name )
                    if self.options.limit != 0:
                        if len(self.stat_analyzed_files) >= self.options.limit:
                            print( '%d limit reached' % self.options.limit )
                            break
        analyzed_count= len(self.stat_analyzed_files)
        issue_file_count= len(self.stat_issue_files)
        print( 'Analyzed: %d files' % analyzed_count )
        print( 'Issues: %d (%d files)' % (self.stat_total_issues,issue_file_count), flush=True )
        result_file_name= 'analyzer_stat.json'
        self.save_json( result_file_name, {
                'analyzed_count': analyzed_count,
                'issue_file_count': issue_file_count,
                'total_issues': self.stat_total_issues,
                'time': self.stat_analyze_time,
                'root': self.options.project if self.options.project else self.options.root
            })
        if self.options.debug:
            self.assistant.stat_dump()

    #--------------------------------------------------------------------------

    def get_root_folder( self ):
        if self.options.project:
            return  self.options.project
        return  self.options.root

    def f_save_list( self ):
        if self.file_list is None:
            self.file_list= self.get_file_list( self.get_root_folder() )
        self.save_list( self.options.list_file, self.file_list )

    def f_load_list( self ):
        list_file= self.options.list_file
        if list_file.endswith( '.json' ):
            self.file_list,self.file_map= self.load_json( list_file )
        else:
            self.file_list,self.file_map= self.load_list( list_file )

    def f_clear_logdir( self ):
        log_dir= self.options.log_dir
        if os.path.exists( log_dir ):
            import shutil
            shutil.rmtree( log_dir )

    #--------------------------------------------------------------------------

    def f_analyze( self ):
        if self.file_list is None:
            self.file_list= self.get_file_list( self.get_root_folder() )
        self.analyze( self.file_list )

    #--------------------------------------------------------------------------

    def f_post( self ):
        post_tool= PostTool( self.options )
        post_tool.post_all()


#------------------------------------------------------------------------------

class PostTool:
    def __init__( self, options ):
        self.options= options
        token= os.environ.get( 'SLACK_API_TOKEN', None )
        if token is None:
            print( 'SLACK_API_TOKEN not found in environment variables.' )
            return
        self.api= SlackAPI.SlackAPI( token, self.options.cache_file, self.options.nossl )
        self.alias= None

    def post_message( self, channel_name, text, blocks=None, markdown_text=None, parent_response= None ):
        thread_ts= None
        if parent_response:
            thread_ts= parent_response.get('ts', None)
        return  self.api.post_message( channel_name, text, blocks, markdown_text, thread_ts )

    def load_json( self, file_name ):
        if os.path.exists( file_name ):
            print( 'load:', file_name )
            with open( file_name, 'r', encoding='utf-8' ) as fi:
                return  json.loads( fi.read() )
        return  None

    def user_alias( self, user_list ):
        user_list= ['@'+user for user in user_list]
        if self.alias is None:
            self.alias= self.load_json( self.options.alias_file )
        if self.alias:
            result_list= []
            for user in user_list:
                result_list.append( '<'+self.alias.get( user, user )+'>' )
            return  result_list
        user_list= ['<'+user+'>' for user in user_list]
        return  user_list

    def post_info( self ):
        result= self.load_json( 'analyzer_stat.json' )
        if result is None:
            return
        issue_count= result.get('total_issues',0)
        if issue_count != 0:
            text_title= '🟥 AI Review: %s' % result.get('time','')
        else:
            text_title= '🟦 AI Review: %s' % result.get('time','')
        text= ''
        text+= '*root*: %s\n' % result.get('root','')
        text+= '*analyzed*: %d files\n' % result.get('analyzed_count',0)
        text+= '*issues*: %d (%d files)\n' % (issue_count,result.get('issue_file_count',0))
        blocks= [
            {
                'type': 'header',
                'text': {
                    'type': 'plain_text',
                    'text': text_title,
                    'emoji': True,
                },
            },
            {
                'type': 'divider'
            },
            {
                'type': 'section',
                'expand': True,
                'text': {
                    'type': 'mrkdwn',
                    'text': text,
                },
            },
        ]
        self.post_message( self.options.channel, text=text_title+'\n'+text, blocks=blocks )

    def post_1( self, log_file_name ):
        analyzed_obj= TextLoader.TextLoader().load( log_file_name )
        default_obj= analyzed_obj.get( 'default', None )
        if default_obj is None:
            return
        file_name_full= default_obj.get( 'file_name', '' )
        base_file_name= os.path.basename(file_name_full)
        issue_count= default_obj.get( 'issue_count', 0 )
        if issue_count == 0:
            print( 'skip: %s' % file_name_full )
            return

        user_menthon= ''
        user_list= default_obj.get( 'users', [] )
        if self.options.use_mention:
            slack_user_list= self.user_alias( user_list )
            print( 'USER',slack_user_list, flush=True )
            user_menthon= ' '.join( slack_user_list )


        text_title= '*%s*  (%d)\n' % (base_file_name,issue_count)

        body= '\n'
        if base_file_name != file_name_full:
            body+= '- %s\n' % file_name_full
        body+= '- %s\n' % ' '.join( user_list )
        body+= '\n'
        for issue_id in range(1,issue_count+1):
            obj= {}
            key= 'issue_%d' % issue_id
            if key in analyzed_obj:
                obj= analyzed_obj[key]
            title= obj.get( 'title', '' )
            file_name= obj.get( 'file_name', '' )
            if file_name != base_file_name:
                body+= '%d. %s (%s)\n' % (issue_id,title,file_name)
            else:
                body+= '%d. %s\n' % (issue_id,title)
        text= user_menthon + '\n' + text_title + body
        blocks= [
            {
                'type': 'section',
                'expand': True,
                'text': {
                    'type': 'mrkdwn',
                    'text': text,
                },
            },
        ]
        response= self.post_message( self.options.channel, text=text, blocks=blocks )

        for issue_id in range(1,issue_count+1):
            obj= {}
            key= 'issue_%d' % issue_id
            if key in analyzed_obj:
                obj= analyzed_obj[key]
            title= obj.get( 'title', '' )
            file_name= obj.get( 'file_name', '' )
            description= obj.get( 'description', '' )
            date= obj.get( 'date', None )
            rev= obj.get( 'rev', None )
            text=  '# 🔴 %d. %s\n\n' % (issue_id,title)
            text+= '- %s\n\n' % file_name
            if date:
                text+= '更新日: %s\n\n' % date
            text+= '## 内容\n\n'
            text+= description + '\n\n　\n'
            response= self.post_message( self.options.channel, text=None, blocks=None, markdown_text=text, parent_response=response )

        text= '# 🔵 %s\n\n' % file_name
        text+= '%s\n\n' % default_obj.get('response','')
        response= self.post_message( self.options.channel, text=None, blocks=None, markdown_text=text, parent_response=response )

    def post_all( self ):
        if os.path.exists( self.options.log_dir ):
            self.post_info()
            with os.scandir( self.options.log_dir ) as di:
                for entry in di:
                    if entry.name.startswith( '.' ) or not entry.is_file():
                        continue
                    _,ext= os.path.splitext( entry.name )
                    if ext == '.txt':
                        full_path= os.path.join( self.options.log_dir, entry.name )
                        self.post_1( full_path )
            self.api.save_cache()


#------------------------------------------------------------------------------

def usage():
    print( 'CodeAnalyzer v1.21 Hiroyuki Ogasawara' )
    print( 'usage: CodeAnalyzer [<options>]' )
    print( 'options:' )
    print( '  --root <root_folder>        default .' )
    print( '  --project <project_folder>  default None' )
    print( '  --engine <engine_folder>    default None' )
    print( '  --list <sources_list>       default list.txt' )
    print( '  --log_dir <output_folder>   default logs' )
    print( '  --preset <preset_name>      default cppreview' )
    print( '  --prompt_dir <prompt_dir>   default .' )
    print( '  --config <config.txt>       default config.txt' )
    print( '  --user_alias <alias_json>   default None' )
    print( '  --limit <max_sources>       default 0' )
    print( '  --use_mention' )
    print( '  --save_list' )
    print( '  --load_list' )
    print( '  --clear' )
    print( '  --analyze' )
    print( '  --post <channel>' )
    print( '  --nossl' )
    print( '  --debug' )
    print( 'ex. CodeAnalyzer.py --root PROJECT_ROOT --analyze' )
    print( 'ex. CodeAnalyzer.py --project PROJECT_ROOT --engine ENGINE_ROOT --analyze' )
    print( 'ex. CodeAnalyzer.py --root PROJECT_ROOT --save_list' )
    print( 'ex. CodeAnalyzer.py --load_list --root PROJECT_ROOT --analyze' )
    print( 'ex. CodeAnalyzer.py --log_dir LOG_DIR --post CHANNEL' )
    sys.exit( 1 )


def main( argv ):
    options= AnalyzerOption()
    func_list= []
    acount= len(argv)
    ai= 1
    while ai < acount:
        arg= argv[ai]
        if arg[0] == '-':
            if arg == '--root':
                ai= options.set_str( ai, argv, 'root' )
            elif arg == '--project':
                ai= options.set_str( ai, argv, 'project' )
            elif arg == '--engine':
                ai= options.set_str( ai, argv, 'engine' )
            elif arg == '--list':
                ai= options.set_str( ai, argv, 'list_file' )
            elif arg == '--log_dir':
                ai= options.set_str( ai, argv, 'log_dir' )
            elif arg == '--prompt_dir':
                ai= options.set_str( ai, argv, 'prompt_dir' )
            elif arg == '--config':
                ai= options.set_str( ai, argv, 'config_file' )
            elif arg == '--preset':
                ai= options.set_str( ai, argv, 'preset' )
            elif arg == '--user_alias':
                ai= options.set_str( ai, argv, 'alias_file' )
            elif arg == '--limit':
                ai= options.set_int( ai, argv, 'limit' )
            elif arg == '--post':
                ai= options.set_str( ai, argv, 'channel' )
                func_list.append( 'f_post' )
            elif arg == '--clear_logdir' or arg == '--clear':
                func_list.append( 'f_clear_logdir' )
            elif arg == '--save_list':
                func_list.append( 'f_save_list' )
            elif arg == '--load_list':
                func_list.append( 'f_load_list' )
            elif arg == '--analyze':
                func_list.append( 'f_analyze' )
            elif arg == '--nossl':
                options.nossl= True
            elif arg == '--use_mention':
                options.use_mention= True
            elif arg == '--debug':
                options.debug= True
            else:
                print( 'Error: unknown option %s' % arg )
                usage()
        else:
            usage()
        ai+= 1

    if func_list != []:
        api= CodeAnalyzer( options )
        for func_name in func_list:
            if hasattr( api, func_name ):
                getattr( api, func_name )()
            else:
                usage()
    else:
        usage()

    return  0


if __name__=='__main__':
    sys.exit( main( sys.argv ) )


