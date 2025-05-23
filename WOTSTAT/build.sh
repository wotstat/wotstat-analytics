#!/bin/bash

MOD_NAME="mod.wotStat"
d=false

while getopts "v:d" flag
do
    case "${flag}" in
        v) v=${OPTARG};;
        d) d=true;;
    esac
done


rm -rf ./build
mkdir ./build
cp -r ./res ./build

configPath="./build/res/scripts/client/gui/mods/wot_stat/common/config.py"
echo -e "version = '$v'\n$(cat $configPath)" > $configPath

utilsPath="./build/res/scripts/client/gui/mods/wot_stat/utils.py"
if [ "$d" = true ]; then
    echo "Building DEBUG version."
    echo -e "DEBUG_MODE = True\n$(cat $utilsPath)" > $utilsPath
else
    echo "Building RELEASE version."
    echo -e "DEBUG_MODE = False\n$(cat $utilsPath)" > $utilsPath
fi

python2 -m compileall ./build

meta=$(<meta.xml)
meta="${meta/\{\{VERSION\}\}/$v}"

cd ./build
echo "$meta" > ./meta.xml

folder=$MOD_NAME"_$v.wotmod"

rm -rf $folder

zip -dvr -0 -X $folder res -i "*.pyc"
zip -vr -0 -X $folder meta.xml
zip -vr -0 -X $folder res -i "*.png"

cd ../
cp ./build/$folder $folder
rm -rf ./build
cp $folder $MOD_NAME"_$v.mtmod"