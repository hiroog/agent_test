# 2025/08/16 Hiroyuki Ogasawara
# vim:ts=4 sw=4 et:

import sys
import os
import re

lib_path= os.path.dirname(__file__)
if lib_path not in sys.path:
    sys.path.append( lib_path )
import Assistant
import FileListLib
import Functions
import TextLoader
from OllamaAPI4 import OptionBase, ExecTime

#------------------------------------------------------------------------------

class AnalyzerOption(OptionBase):
    def __init__( self, **args ):
        super().__init__()
        self.root= None
        self.project= None
        self.engine= None
        self.list_file= 'list.txt'
        self.output_folder= 'logs'
        self.preset= 'cppreview'
        self.debug= False
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

#------------------------------------------------------------------------------

class CodeAnalyzer:
    def __init__( self, options ):
        self.options= options
        self.file_list= None

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
        return  file_list

    #--------------------------------------------------------------------------

    def get_file_list( self, root ):
        file_list= FileListLib.FileListLib( '.code_analyzer_ignore' )
        file_list= file_list.find_file( root )
        cpp_pat= re.compile( r'\.(c|cpp|h|hpp|inl)$' )
        file_list2= []
        for file_name in file_list:
            pat= cpp_pat.search( file_name )
            if pat:
                file_list2.append( file_name )
        return  file_list2

    #--------------------------------------------------------------------------

    # ====== default
    # S file_name SOURCE
    # A sources SOURCE1 SOURCE2
    # ====T response
    # ～
    # ====== issue_1
    # S file_name SOURCE
    # ====T title
    # ～
    # ====T description
    # ～

    def save_logs( self, response, prompt, file_list, issue_list ):
        log_obj= {
                'default': {
                    'response': response,
                    'file_name': file_list[0],
                    'sources': file_list,
                }
            }
        for issue in issue_list.logs:
            issue_id= issue[0]
            issue_name= 'issue_%d' % issue_id
            issue_obj= {
                'issue_id': issue_id,
                'title': issue[1],
                'file_name': issue[2],
                'description': issue[3],
            }
            log_obj[issue_name]= issue_obj


        output_folder= self.options.output_folder
        if not os.path.exists( output_folder ):
            os.makedirs( output_folder )
        output_file= '%s/%s.txt' % (output_folder, os.path.basename(file_list[0]) )
        TextLoader.TextLoader().save( output_file, log_obj )

    def analyze_1( self, root, file_list ):
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

        options= Assistant.AssistantOptions()
        if self.options.debug:
            options.print= True
            options.debug_echo= True

        issue_list= IssueList()
        Functions.issue_list= issue_list

        with ExecTime( 'Generate' ):
            assistant= Assistant.Assistant( options )
            response,status_code,prompt= assistant.generate_chain( input_obj )

        if status_code != 200:
            return  False

        self.save_logs( response, prompt, file_list, issue_list )
        return  True

    def analyze( self, root, file_list ):
        with ExecTime( 'Analyze' ):
            file_set= set(file_list)
            analyze_count= 0
            for file_name in file_list:
                base,ext= os.path.splitext( file_name )
                if ext == '.cpp':
                    analyze_list= [ file_name ]
                    header_file= base + '.h'
                    if header_file in file_set:
                        analyze_list.append( header_file )
                    if not self.analyze_1( root, analyze_list ):
                        break
                    analyze_count+= 1
            print( 'Analyze: %d files' % analyze_count )

    #--------------------------------------------------------------------------

    def f_save_list( self ):
        list_file= self.options['list_file']
        self.file_list= self.file_list()
        self.save_list( list_file, self.file_list )

    def f_load_list( self ):
        list_file= self.options['list_file']
        self.file_list= self.load_list( list_file )

    #--------------------------------------------------------------------------

    def get_source_folder( self ):
        if self.options.root:
            return  self.options.root
        if self.options.project:
            return  self.options.project
        return  '.'

    def f_analyze( self ):
        root= self.get_source_folder()
        if self.file_list is None:
            self.file_list= self.get_file_list( root )
        self.analyze( root, self.file_list )


#------------------------------------------------------------------------------

def usage():
    print( 'CodeAnalyzer v1.00' )
    print( 'usage: CodeAnalyzer [<options>]' )
    print( 'options:' )
    print( '  --root <root_folder>        default .' )
    print( '  --project <project_folder>  default None' )
    print( '  --engine <engine_folder>    default None' )
    print( '  --list <sources_list>       default list.txt' )
    print( '  --output <output_folder>    default logs' )
    print( '  --preset <preset_name>      default cppreview' )
    print( '  --save_list' )
    print( '  --load_list' )
    print( '  --analyze' )
    print( '  --debug' )
    print( 'ex. CodeAnalyzer.py --root PROJECT_ROOT --analyze' )
    print( 'ex. CodeAnalyzer.py --project PROJECT_ROOT --engine ENGINE_ROOT --analyze' )
    print( 'ex. CodeAnalyzer.py --root PROJECT_ROOT --save_list' )
    print( 'ex. CodeAnalyzer.py --load_list --analyze' )
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
            elif arg == '--output':
                ai= options.set_str( ai, argv, 'output_folder' )
            elif arg == '--preset':
                ai= options.set_str( ai, argv, 'preset' )
            elif arg == '--save_list':
                func_list.append( 'f_save_list' )
            elif arg == '--load_list':
                func_list.append( 'f_load_list' )
            elif arg == '--analyze':
                func_list.append( 'f_analyze' )
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


