# vim:ts=4 sw=4 et:

USE_SLACK=0

USE_TEXTLOADER=1
USE_TEST01=1
USE_TEST02=1
USE_TEST03=1
USE_TEST04=1
USE_TEST05=1
USE_TEST10=1
USE_ASSISTANT1=1
USE_CPPREVIEW=1
USE_SLACKBOT=1

#------------------------------------------------------------------------------

export PYTHONPATH=test
set -e

#------------------------------------------------------------------------------

BOTVENV_DIR=botenv
SLACKENV_FILE=../setenv.sh
CONFIG_FILE=config.sample.txt

if [ -e $BOTVENV_DIR ]; then
    . $BOTVENV_DIR/bin/activate
fi

if [ -e $SLACKENV_FILE ]; then
    . $SLACKENV_FILE
fi

BASE_OPTIONS="--config $CONFIG_FILE --print --debug"

#------------------------------------------------------------------------------

if [ $USE_TEXTLOADER = 1 ];then
python3 TextLoader.py test/data_sample.json --test
python3 TextLoader.py test/test_config.txt --test
fi

#------------------------------------------------------------------------------

# tool calling
if [ $USE_TEST01 = 1 ];then
python3 Assistant.py $BASE_OPTIONS --preset test01 --input input/test01.txt
fi
if [ $USE_TEST02 = 1 ];then
python3 Assistant.py $BASE_OPTIONS --preset test02 --input input/test02.json
fi

# inline propt
if [ $USE_TEST03 = 1 ];then
python3 Assistant.py $BASE_OPTIONS --preset test03
fi

# preset
if [ $USE_TEST04 = 1 ];then
python3 Assistant.py $BASE_OPTIONS                 --input input/test04.txt
fi

# include
if [ $USE_TEST05 = 1 ];then
python3 Assistant.py $BASE_OPTIONS --preset test05
fi

# complex tool calling
if [ $USE_TEST10 = 1 ];then
  if [ -e local/flatlib5 ];then
python3 Assistant.py $BASE_OPTIONS --preset test10 --input input/test10.txt
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
python3 Assistant.py $BASE_OPTIONS --preset assistant1 $POST_FLAG
fi

#------------------------------------------------------------------------------

if [ $USE_CPPREVIEW = 1 ];then
python3 CodeAnalyzer.py $BASE_OPTIONS --list test/test_list.txt --load_list --root input --analyze $POST_FLAG
fi

#------------------------------------------------------------------------------

if [ $USE_SLACKBOT = 1 ];then
  if [ "$SLACK_BOT_TOKEN" != "" ];then
    if [ "$SLACK_APP_TOKEN" != "" ];then
      if [ -e local/skills ];then
python3 DebugCLI.py $BASE_OPTIONS --text "jenkinsの状態を見たい"
      fi
    fi
  fi
fi

