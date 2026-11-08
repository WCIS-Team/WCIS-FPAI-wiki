ekho 普通话三声线试听（2026-11-02，已按你的话只留普通话）
引擎：S:/work/WCIS/repos/ekho-linux 的 out/ekho（今日从本仓 HEAD 编出的 x86-64 二进制，跑在 WSL）
格式：48 kHz / 2 ch / 16 bit WAV；语速默认（tempo delta 0）

文本
  short：今天天气不错，我们出去走走吧。
  long ：他说这本书写得真好，我一口气看了三遍，还是想再看一遍。

清单一：01/02/03 三个普通话目录，每个都是同一段文本
  01-mandarin-current  zh-current-short.wav  3.04 s   现在用的声（huang），仓库里的 48 kHz 包
                       zh-current-long.wav   5.39 s
  02-mandarin-baker    zh-baker-short.wav    3.73 s   ekho 9.0 的新普通话声（baker），22050 Hz 源头
                       zh-baker-long.wav     5.45 s
  03-mandarin-yali     zh-yali-short.wav     3.55 s   另一个人声（yali），44.1 kHz 源头，现役没在用
                       zh-yali-long.wav       6.52 s

二、现用声是 huang（实测）
  仓库的 ekho-data/pinyin.voice.44k（md5 e9632c7f4ad3c829b5880699b16a2a39）
  与用 pinyin-huang-44100-wav-v3 现场生成的包 逐字节相同；现役 48 kHz 包
  ekho-data/pinyin.voice（136,359,454 B）就是它转出来的。
  对照：yali 生成的包 md5 832dfdb84f8f20a0d7b2d6112d492b4c（63,679,170 B），与现役包不同。

三、已删（2026-11-02 15:10，全部进回收站，可还原）
  桌面：04-cantonese、05-toisanese、06-hakka、07-tibetan、08-korean、09-english 六个目录
  仓库 ekho-data：jyutping/、jyutping.index、jyutping.voice、zhy.dict、zhy_list、
    toisanese/、toisanese_list、hakka/、ka_list、bo_list、ko_list、
    hangul/、ngangien/、ngangien_list
  留下的是普通话：zh.dict、zh_list、zh_listx、zh_patch、friso-dict、alphabet、
    pinyin/、pinyin.index(.44k/.8k)、pinyin.voice(.44k/.8k)

四、删完之后的状态
  普通话合成正常（删后冒烟：同一句 387,128 B）。
  仓库里那 12 个被删的 tracked 文件在 git status 里是 D，未提交。
  需要你知道的连带影响（我没动脚本/文档）：
    scripts/sim.sh        有 1 处粤语用例
    scripts/make-samples.sh 有整节 02-yue-cantonese（5 处）
    scripts/fetch-voice.sh  有粤语抓取段（会重新下回 jyutping.voice 与 wav 树）
    README.md             三处仍写着 Cantonese（含 /voices 列表）
    板端 /root/ekho-bench/p48 仍是旧数据（粤语等还在），本轮没动板子
