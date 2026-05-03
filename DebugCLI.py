# 2026/05/02 Hiroyuki Ogasawara
# vim:ts=4 sw=4 et:

import sys
import os
import time
import math
import platform

if platform.system() != 'Windows':
    import readline

lib_path= os.path.dirname(__file__)
if lib_path not in sys.path:
    sys.path.append( lib_path )
import SlackBot

#------------------------------------------------------------------------------

class SlackCLI:
    def __init__( self, options ):
        self.bot= SlackBot.SlackBot( options )

    #--------------------------------------------------------------------------
    # Debug CLI

    def cli_thread( self ):
        t= time.time()
        thread_id= time.strftime( 'cli_%Y%m%d_%H%M%S', time.localtime(t) )
        f= t-math.floor(t)
        thread_id+= '_%07d' % ((int)(f * 10000000))
        print( thread_id )
        while True:
            print( 'Robo> ', end='' )
            line= input()
            if line.strip() != '':
                prompt= 'USER: ' + line
                result= self.bot.bot( thread_id, prompt, '', {} )
                print( '\U0001f916 ****************' )
                print( result )
                print( '*******************' )


#------------------------------------------------------------------------------

def usage():
    print( 'DebugCLI v1.00 Hiroyuki Ogasawara' )
    print( 'usage: DebugCLI [<options>' )
    print( 'options:' )
    print( '  --preset <preset>             default: chatbot' )
    print( '  --config <config_file>        default: config.txt' )
    print( '  --prompt_dir <dir>' )
    print( '  --print' )
    print( '  --debug' )
    sys.exit( 1 )


def main( argv ):
    acount= len(argv)
    options= SlackBot.SlackBotOptions()
    ai= 1
    while ai < acount:
        arg= argv[ai]
        if arg[0] == '-':
            if arg == '--preset':
                ai= options.set_str( ai, argv, 'preset' )
            elif arg == '--config':
                ai= options.set_str( ai, argv, 'config_file' )
            elif arg == '--prompt_dir':
                ai= options.set_str( ai, argv, 'prompt_dir' )
            elif arg == '--print':
                options.print= True
            elif arg == '--debug':
                options.debug_echo= True
            else:
                print( 'Error: unknown option %s' % arg )
                usage()
            ai+= 1
        else:
            usage()

    slack_bot= SlackCLI( options )
    slack_bot.cli_thread()
    return  0

if __name__ == '__main__':
    sys.exit( main( sys.argv ) )


