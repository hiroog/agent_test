# vim:ts=4 sw=4 et:

USE_SLACK=0

USE_TEST01=1
USE_TEST02=1
USE_TEST03=1
USE_TEST04=1
USE_TEST05=1
USE_TEST10=1
USE_ASSISTANT1=1
USE_CPPREVIEW=1
USE_SLACKBOT=0

#------------------------------------------------------------------------------

BOTVENV_DIR=botenv
SLACKENV_FILE=../setenv.sh
CONFIG_FILE=test/test_config.txt

if [ -e $BOTVENV_DIR ]; then
    . $BOTVENV_DIR/bin/activate
fi

if [ -e $SLACKENV_FILE ]; then
    . $SLACKENV_FILE
fi

#------------------------------------------------------------------------------

# tool calling
if [ $USE_TEST01 = 1 ];then
python3 Assistant.py --config $CONFIG_FILE --preset test01 --input input/test01.txt --print --debug
fi
if [ $USE_TEST02 = 1 ];then
python3 Assistant.py --config $CONFIG_FILE --preset test02 --input input/test02.txt --print --debug
fi

# inline propt
if [ $USE_TEST03 = 1 ];then
python3 Assistant.py --config $CONFIG_FILE --preset test03                          --print --debug
fi

# input
if [ $USE_TEST04 = 1 ];then
python3 Assistant.py --config $CONFIG_FILE                 --input input/test04.txt --print --debug
fi

# include
if [ $USE_TEST05 = 1 ];then
python3 Assistant.py --config $CONFIG_FILE --preset test05                          --print --debug
fi

# complex tool calling
if [ $USE_TEST10 = 1 ];then
  if [ -e src/flatlib5 ];then
python3 Assistant.py --config $CONFIG_FILE --preset test10 --input input/test10.txt --print --debug
  fi
fi

#------------------------------------------------------------------------------

POST_FLAG=
if [ $USE_SLACK = 1 ];then
  if [ "$SLACK_API_TOKEN" != "" ];then
      POST_FLAG="--post apptest"
  fi
fi

if [ $USE_ASSISTANT1 = 1 ];then
python3 Assistant.py --config $CONFIG_FILE --preset assistant1 --print --debug $POST_FLAG
fi

#------------------------------------------------------------------------------

if [ $USE_CPPREVIEW = 1 ];then
python3 CodeAnalyzer.py --config $CONFIG_FILE --list test/test_list.txt --load_list --root input --analyze --debug $POST_FLAG
fi

#------------------------------------------------------------------------------

if [ $USE_SLACKBOT = 1 ];then
if [ $USE_SLACK = 1 ];then
  if [ "$SLACK_BOT_TOKEN" != "" ];then
    if [ "$SLACK_APP_TOKEN" != "" ];then
python3 SlackBot.py --config $CONFIG_FILE --print --debug
    fi
  fi
fi
fi

