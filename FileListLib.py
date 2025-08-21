# 2018/01/14 Hiroyuki Ogasawara
# vim:ts=4 sw=4 et:

import  os
import  sys
import  re


class Logger:
    def __init__( self ):
        self.DebugOutput= False
        self.indent= 0

    def d( self, text ):
        if self.DebugOutput:
            print( (' ' * self.indent) + str(text) )

    def set( self, indent ):
        self.indent= indent

    def push( self ):
        self.indent+= 2

    def pop( self ):
        self.indent-= 2

Log= Logger()


class IgnorePattern:
    def __init__( self, file_name ):
        self.pattern_list= []
        self.multi_list= []
        self.current_list= []
        self.include_list= []
        if file_name is not None:
            self.load( file_name )

    def isMultiFolderPattern( self, pat ):
        return  '/' in pat.strip( '^$' ).strip( '/' )

    def load( self, file_name ):
        Log.d( 'Load ' + file_name )
        with open( file_name, 'r', encoding= 'utf-8' ) as fi:
            for line in fi:
                if line[0] == '\n' or line[0] == '#':
                    continue
                line= line.strip()
                if line[0] == '!':
                    self.include_list.append( re.compile( line[1:] ) )
                elif line[0] == '^':
                    self.current_list.append( re.compile( line ) )
                elif self.isMultiFolderPattern( line ):
                    self.multi_list.append( re.compile( line ) )
                else:
                    self.pattern_list.append( re.compile( line ) )
        self.dump()

    def dump( self ):
        Log.d( 'include:' )
        Log.push()
        for pattern in self.include_list:
            Log.d( pattern )
        Log.pop()
        Log.d( 'pattern:' )
        Log.push()
        for pattern in self.pattern_list:
            Log.d( pattern )
        Log.pop()
        Log.d( 'multi:' )
        Log.push()
        for pattern in self.multi_list:
            Log.d( pattern )
        Log.pop()
        Log.d( 'current:' )
        Log.push()
        for pattern in self.current_list:
            Log.d( pattern )
        Log.pop()

    def search_include( self, file_name ):
        for pattern in self.include_list:
            #Log.d( ' *compI ' + str(pattern) + '  ' + file_name )
            pat= pattern.search( file_name )
            if pat is not None:
                Log.d( 'Include  <' + str(pattern) + '>  "' + file_name + '"' )
                return  pat
        return  None

    def search_multi( self, file_name ):
        for pattern in self.multi_list:
            #Log.d( ' *compM ' + str(pattern) + '  ' + file_name )
            pat= pattern.search( file_name )
            if pat is not None:
                Log.d( 'IGNORE M <' + str(pattern) + '>  "' + file_name + '"' )
                return  pat
        return  None

    def search_pattern( self, file_name ):
        for pattern in self.pattern_list:
            #Log.d( ' *compP ' + str(pattern) + '  ' + file_name )
            pat= pattern.search( file_name )
            if pat is not None:
                Log.d( 'IGNORE P <' + str(pattern) + '>  "' + file_name + '"' )
                return  pat
        return  None

    def search_current( self, file_name ):
        for pattern in self.current_list:
            #Log.d( ' *compC ' + str(pattern) + '  ' + file_name )
            pat= pattern.search( file_name )
            if pat is not None:
                Log.d( 'IGNORE C <' + str(pattern) + '>  "' + file_name + '"' )
                return  pat
        return  None


class PatternStack:
    def __init__( self ):
        self.stack= []

    def push( self, file_name= None ):
        self.stack.append( IgnorePattern( file_name ) )

    def pop( self ):
        self.stack.pop()

    def search( self, file_name ):
        if self.stack != []:
            if self.stack[-1].search_include( file_name ) is not None:
                return  None

        for pattern in self.stack:
            pat= pattern.search_pattern( file_name )
            if pat is not None:
                return  pat
        if self.stack != []:
            return  self.stack[-1].search_current( file_name )
        return  None

    def search_stacktop( self, file_name ):
        if self.stack != []:
            stack_top= self.stack[-1]
            #if stack_top.search_include( file_name ) is not None:
            #    return  None
            pat= stack_top.search_multi( file_name )
            if pat is not None:
                return  pat
            return  stack_top.search_current( file_name )
        return  None


class FileListLib:
    def __init__( self, ignore_file= None ):
        self.stack= PatternStack()
        self.ignore_file= ignore_file
        self.preload_file= None

    def find_file( self, root ):
        Log.push()
        Log.d( 'Enter [' + root + '/]' )
        Log.push()
        file_list= []
        #with os.scandir( root ) as di:
        di= os.scandir( root )
        #ignore_pushed= False
        if self.ignore_file:
            ignore_file= os.path.join( root, self.ignore_file )
            if os.path.exists( ignore_file ):
                self.stack.push( ignore_file )
                #ignore_pushed= True
            else:
                self.stack.push()
        else:
            self.stack.push( self.preload_file )
            self.preload_file= None
        start_offset= len(root)
        for entry in di:
            file_name= entry.name
            full_name= os.path.join( root, entry.name ).replace( '\\', '/' )
            if entry.is_dir():
                if self.stack.search( '/' + file_name + '/' ) is None:
                    result_list= self.find_file( full_name )
                    for file in result_list:
                        if self.stack.search_stacktop( file[start_offset:] ) is None:
                            file_list.append( file )
            else:
                if self.stack.search( '/' + file_name ) is None:
                    file_list.append( full_name )
        #if ignore_pushed:
        self.stack.pop()
        Log.pop()
        Log.d( 'Leave [' + root + '/]' )
        Log.pop()
        return  file_list

    def find_file_preload( self, root, file_name ):
        self.preload_file= file_name
        self.ignore_file= None
        return  self.find_file( root )


def main( argv ):
    import  time
    #Log.DebugOutput= True
    start_time= time.perf_counter()
    fll= FileListLib( '.flignore' )
    file_list= fll.find_file( '.' )
    print( 'pass: %d files (%.2f sec)' % (len(file_list), time.perf_counter() - start_time) )
    with open( 'output.log', 'w', encoding='utf-8' ) as fo:
        fo.write( '=============\n' )
        for name in file_list:
            fo.write( name + '\n' )
            #print( name )
        fo.write( 'file=%d\n' % len(file_list) )
        #print( 'file=%d' % len(file_list) )


if __name__ == '__main__':
    main( sys.argv )



