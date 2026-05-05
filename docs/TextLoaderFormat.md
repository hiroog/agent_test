# TextLoader フォーマット

json や yaml 等と同じように、辞書構造のデータを保持することができます。
特徴は複数行にわたるテキストを直接埋め込めることです。

設定などのキーと一緒に LLM 向けのプロンプトに使う Markdown を見やすい形で書き込むことができます。


## 書式

`;;` で始まる行はコメントです。コメント記号に '#' を使わないのは Markdown との干渉を避けるためです。

トップレベルは必ず辞書構造とみなします。


### 1行フォーマット

以下のように型を明示的に指定する必要があります。スペースまたは TAB 区切りです。

| 書式                      | 内容                                 |
|:--------------------------|:-------------------------------------|
| S `<key>` `<value>`       | 文字列                               |
| I `<key>` `<value>`       | 整数値                               |
| F `<key>` `<value>`       | 浮動小数点数                         |
| B `<key>` `<value>`       | Bool 値 (true/false or 1/0)          |
| SA `<key>` `<value>` ..   | 文字列の配列                         |
| A `<key>` `<value>` ..    | 文字列の配列 (SA と同じ、互換性用)   |

例
```
S model Qwen3.5-122B-A10B
F top_p 0.95
```

↓

```json
{
  "model": "Qwen3.5-122B-A10B",
  "top_p": 0.95
}
```



#### SA 配列

`SA` は唯一複数のパラメータを持ち、文字列の配列とみなします。`SA` の代わりに `A` と記述することもできます。

例
```
SA tools  func1  func2  func3
```

↓

```json
{
  "tools": [ "func1", "func2", "func3" ]
}
```


### 複数行テキストフォーマット

```
====T <key>

～data
```

扱いは文字列なので `S <key>` と同じですが、複数行に渡るデータを記述可能で改行がそのまま含まれます。

同じ `====T <key>` または辞書の開始マーク `====== <key>` で終了します。

複数行フォーマットの後に 1行フォーマットでデータを宣言することはできません。
複数行フォーマットは必ず辞書定義の最後に位置します。


```
====T md
# 複数行データの例

このようにテキストをそのまま記述することができます。
```

↓

```json
{
  "md": "# 複数行データの例\n\nこのようにテキストをそのまま記述することができます。\n"
}
```


### 辞書宣言

`=` が 6文字以上続く場合は入れ子になった辞書の宣言とみなします。

つまり

```json
{
  "key": "value",
  "subdict": {
    "key": "value"
  }
}
```

この構造は以下のように記述します。

```
S key value
====== subdict
S key value
```

複数ブロックある場合もそのまま宣言できます。


```json
{
  "key": "toplevel",
  "subdict1": {
    "key1": "sublevel1"
  },
  "subdict2": {
    "key2": "sublevel2"
  }
}
```
↓

```
S key  toplevel
====== subdict1
S key1 sublevel1
====== subdict2
S key2 sublevel2
```

`=` の数で入れ子を表現できます。
現在の辞書の開始で使われた `=` の数よりも多い場合はネストとみなします。
現在の辞書の開始で使われた `=` の数よりも少ない場合は親の宣言に戻ります。


```json
{
  "key": "topvalue",
  "nest1": {
    "key1": "nestvalue1"
    "nest2": {
      "key2": "nestvalue2"
    }
  }
}
```
↓

```
S key  topvalue
====== nest1
S key1 nestvalue1
======== nest2
S key2 nestvalue2
```


```json
{
  "key": "value",
  "subdict1": {
    "key1": "subvalue1"
    "nest1": {
      "nkey": "nestvalue"
    }
  },
  "subdict2": {
    "key2": "subvalue2"
  }
}
```
↓

```
S key  value
====== subdict1
S key1 subvalue1
======== nest1
S nkey nestvalue
====== subdict2
S key2 subvalue2
```

入れ子構造が分かりにくいですが、あまり複雑な階層構造は想定せず、インデントなしに複数行のテキスト `====T` を必ず行頭から記述できるようにすることが目的となっています。


### json との互換性

配列や文字列の扱いに制限があるため json とは下位互換となります。
TextLoader のフォーマットは json に変換できますが、逆は必ずしもできません。



## コマンドラインからの使いかた

### TextLoader to json

```bash
python TextLoader.py  input.json  -o output.txt
```

### json to TextLoader

```bash
python TextLoader.py  input.txt  -o output.json
```



## Module として使う場合

```python
import TextLoader

obj= TextLoader.TextLoader().load( 'load_name.txt' )

TextLoader.TextLoader().save( 'save_name.txt', obj )
```



