# WOTMOD
## Общая информация
Этот репозиторий содержит всё необходимое для разработки мода для танков.
* WGMods: https://wgmods.net/5652/


## Мод
От релизной версии он отличается файлом wot_stat/common/crypto.py, сейчас в нём расположена заглушка, релизная версия кодирует отправляемый на сервер json, дабы усложнить жизнь желающим заспамить сервер фейковыми сообщениями.

## Структура
Задача [eventLogger](res/scripts/client/gui/mods/wot_stat/logger/eventLogger.py) -- создавать события [events](res/scripts/client/gui/mods/wot_stat/logger/events.py) и добавлять их в [battleEventSession](wotstat/res/scripts/client/gui/mods/wot_stat/logger/battleEventSession.py).

[BattleEventSession](res/scripts/client/gui/mods/wot_stat/logger/battleEventSession.py) группирует события и раз в N=5 секунд отправляет их на сервер. Каждый бой создаётся новый экземпляр `BattleEventSession(Events.OnEndLoad())`, все события внутри этого боя отправляются через этот экземпляр. Экземпляр завершает своё существование событием `Events.OnBattleResult()`.

Все остальные файлы служебные и не выполняют ключевой роли. 

## События
| Событие         | Статус |  Описание                                 |
|----------       |:------:|:------                                    | 
| OnBattleStart   |  [x]   | Начало боя                                |  
| OnShot          |  [x]   | Факт совершения выстрела                  |
| OnBattleResult  |  [x]   | Результат боя                             |


## Тестовый сервер
Мод сохраняет события на сервер, если вы хотите протестировать мод локально, вы можете запустить [тестовый сервер](https://github.com/SoprachevAK/wot-stat/tree/main/mod/serverPlaceholder) на NodeJS

1. В папке `World_of_Tanks/mods/configs/wot_stat` создать текстовый файл `config.cfg`, в который прописать 
```
{
    "eventURL": "http://localhost:5000/api/events/send",
    "initBattleURL":"http://localhost:5000/api/events/OnBattleStart"
}
```
2. Запустить serverPlaceholder `npm run serve`
3. Запустить танки
4. Готово. Теперь мод будет отправлять события на локальный сервер. Их можно посмотреть в консоле сервера. 


## Редактирование через PyCharm
Для корректной подсветки синтаксиса в IDE необходимы зависимости танков. 

1. Склонировать репозиторий с подмодулями (`git clone --recursive https://github.com/SoprachevAK/wot-stat.git`)
   * **WorldOfTanks-Decompiled** - исходный код клиента танков
   * **BigWorldPlaceholder** - заглушки функций библиотеки движка, объявлены только те, которые были нужны мне
2. Запустить Zip-Unpacker.exe для исправления регистра названия файлов 
3. Открыть текущую директорию через PyCharm (*File->Open*)
4. Отметить следующие папки как корень исходников (*ПКМ -> Mark Directory as -> Sources Root*)
   * `/WorldOfTanks-Decompiled/source/res/scripts/client`
   * `/WorldOfTanks-Decompiled/source/res/scripts/common`
   * `/BigWorldPlaceholder`
5. Готово. Теперь в IDE будет работать подсветка синтаксиса и подсказка кода.

## Сборка мода
1. С помощью [PjOrion](https://koreanrandom.com/forum/topic/15280-) скомпилировать (Run -> Compile py folder)
2. Запустить Zip-Packer.cmd для получения .wotmod файла
