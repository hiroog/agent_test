@echo off
chcp 65001

set USE_SLACK=0

set USE_TEXTLOADER=1
set USE_TEST01=1
set USE_TEST02=1
set USE_TEST03=1
set USE_TEST04=1
set USE_TEST05=1
set USE_TEST10=1
set USE_TEST20=1
set USE_ASSISTANT1=1
set USE_CPPREVIEW=1
set USE_SLACKBOT=1

rem ---------------------------------------------------------------------------

cd /d %~dp0
cd ..

set PYTHONPATH=test

set SLACKENV_FILE=..\setenv.bat
set CONFIG_FILE=config.sample.txt

if exist %SLACKENV_FILE% call %SLACKENV_FILE%

rem ---------------------------------------------------------------------------

set ARG=%1

if "%ARG%" == "openai" (
set TS_HOST=http://localhost:11434
set TS_MODEL=gpt-oss:120b-cloud
set TS_PROVIDER=openai
)

if "%ARG%" == "ollama" (
set TS_HOST=http://localhost:11434
set TS_MODEL=gpt-oss:120b-cloud
set TS_PROVIDER=ollama
)

if "%ARG%" == "local1" (
set TS_HOST=%TS_HOST_LOCAL1%
set TS_MODEL=%TS_MODEL_LOCAL1%
set TS_PROVIDER=%TS_PROVIDER_LOCAL1%
)

if "%ARG%" == "local2" (
set TS_HOST=%TS_HOST_LOCAL2%
set TS_MODEL=%TS_MODEL_LOCAL2%
set TS_PROVIDER=%TS_PROVIDER_LOCAL2%
)

if "%ARG%" == "local3" (
set TS_HOST=%TS_HOST_LOCAL3%
set TS_MODEL=%TS_MODEL_LOCAL3%
set TS_PROVIDER=%TS_PROVIDER_LOCAL3%
)

if "%TS_HOST%" == "" (
set TS_HOST=http://localhost:1234
set TS_MODEL=qwen/qwen3.5-9b
set TS_PROVIDER=openai
)

set BASE_OPTIONS=--config %CONFIG_FILE% --debug --print --host %TS_HOST% --provider %TS_PROVIDER% --model %TS_MODEL%

rem ---------------------------------------------------------------------------


if %USE_TEXTLOADER% == 1 (
python TextLoader.py test/data_sample.json --test
python TextLoader.py config.sample.txt --test
)

if %USE_TEST01% == 1 python src/Assistant.py %BASE_OPTIONS%  --preset test01 --input input/test01.txt

if %USE_TEST02% == 1 python src/Assistant.py %BASE_OPTIONS%  --preset test02 --input input/test02.json

if %USE_TEST03% == 1 python src/Assistant.py %BASE_OPTIONS%  --preset test03

if %USE_TEST04% == 1 python src/Assistant.py %BASE_OPTIONS%                  --input input/test04.txt

if %USE_TEST05% == 1 python src/Assistant.py %BASE_OPTIONS%  --preset test05

if %USE_TEST10% == 1 (
if exist local/flatlib5 python src/Assistant.py %BASE_OPTIONS%  --preset test10 --input input/test10.txt
)

if %USE_TEST20% == 1 python src/Assistant.py %BASE_OPTIONS%  --preset test20

if %USE_ASSISTANT1% == 1 python src/Assistant.py %BASE_OPTIONS%  --preset assistant1

if %USE_CPPREVIEW% == 1  python src/CodeAnalyzer.py %BASE_OPTIONS%  --list test/test_list.txt  --load_list --root input --analyze

if %USE_SLACKBOT% == 1 (
if exist local/skills python src/DebugCLI.py %BASE_OPTIONS%   --text "jenkinsの状態を見たい"
)


rem ---------------------------------------------------------------------------

pause

