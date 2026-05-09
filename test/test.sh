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
#
#------------------------------------------------------------------------------

ARG1="$1"
if [ "$ARG1" = "" ]; then
ARG1=openai
fi

if [ "$ARG1" = "ollama" ]; then
TS_HOST=http://localhost:11434
TS_PROVIDER=ollama
TS_MODEL=gpt-oss:120b-cloud
fi

if [ "$ARG1" = "openai" ]; then
TS_HOST=http://localhost:11434/v1
TS_PROVIDER=openai
TS_MODEL=gpt-oss:120b-cloud
fi

if [ "$ARG1" = "local1" ]; then
TS_HOST=$TS_HOST_LOCAL1
TS_PROVIDER=$TS_PROVIDER_LOCAL1
TS_MODEL=$TS_MODEL_LOCAL1
fi

if [ "$ARG1" = "local2" ]; then
TS_HOST=$TS_HOST_LOCAL2
TS_PROVIDER=$TS_PROVIDER_LOCAL2
TS_MODEL=$TS_MODEL_LOCAL2
fi

if [ "$ARG1" = "local3" ]; then
TS_HOST=$TS_HOST_LOCAL3
TS_PROVIDER=$TS_PROVIDER_LOCAL3
TS_MODEL=$TS_MODEL_LOCAL3
fi

if [ "$ARG1" = "local4" ]; then
TS_HOST=$TS_HOST_LOCAL4
TS_PROVIDER=$TS_PROVIDER_LOCAL4
TS_MODEL=$TS_MODEL_LOCAL4
fi

if [ "$ARG1" = "local5" ]; then
TS_HOST=$TS_HOST_LOCAL5
TS_PROVIDER=$TS_PROVIDER_LOCAL5
TS_MODEL=$TS_MODEL_LOCAL5
fi


BASE_OPTIONS="--config $CONFIG_FILE --print --debug --host $TS_HOST --provider $TS_PROVIDER --model $TS_MODEL"

#------------------------------------------------------------------------------

if [ $USE_TEXTLOADER = 1 ];then
python3 src/TextLoader.py test/data_sample.json --test
python3 src/TextLoader.py config.sample.txt --test
fi

#------------------------------------------------------------------------------

# tool calling
if [ $USE_TEST01 = 1 ];then
python3 src/Assistant.py $BASE_OPTIONS --preset test01 --input input/test01.txt
fi

# tool calling json
if [ $USE_TEST02 = 1 ];then
python3 src/Assistant.py $BASE_OPTIONS --preset test02 --input input/test02.json
fi

# inline propt
if [ $USE_TEST03 = 1 ];then
python3 src/Assistant.py $BASE_OPTIONS --preset test03
fi

# preset
if [ $USE_TEST04 = 1 ];then
python3 src/Assistant.py $BASE_OPTIONS                 --input input/test04.txt
fi

# include
if [ $USE_TEST05 = 1 ];then
python3 src/Assistant.py $BASE_OPTIONS --preset test05
fi

# complex tool calling
if [ $USE_TEST10 = 1 ];then
  if [ -e local/flatlib5 ];then
python3 src/Assistant.py $BASE_OPTIONS --preset test10 --input input/test10.txt
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
python3 src/Assistant.py $BASE_OPTIONS --preset assistant1 $POST_FLAG
fi

#------------------------------------------------------------------------------

if [ $USE_CPPREVIEW = 1 ];then
python3 src/CodeAnalyzer.py $BASE_OPTIONS --list test/test_list.txt --load_list --root input --analyze $POST_FLAG
fi

#------------------------------------------------------------------------------

if [ $USE_SLACKBOT = 1 ];then
  if [ "$SLACK_BOT_TOKEN" != "" ];then
    if [ "$SLACK_APP_TOKEN" != "" ];then
      if [ -e local/skills ];then
python3 src/DebugCLI.py $BASE_OPTIONS --text "jenkinsの状態を見たい"
      fi
    fi
  fi
fi

