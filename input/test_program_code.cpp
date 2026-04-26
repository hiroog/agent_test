
#include <stdio.h>

int test_function(int a, int b, int c)
{
    return a + b * c;
}


int main(int argc, char** argv)
{
    printf("%d\n", test_function( 123, argc ));
    return 0;
}

