饥荒烹饪食谱图鉴
数据日期：2026-10-14

打开方法
解压完整文件包，双击 index.html。支持 Chrome、Edge、Firefox 等现代浏览器。
所有页面所需图片、脚本、样式均在包内；不需要联网，不需要启动服务器。
不要单独移动 index.html；请保留 assets、data.js、app.js、style.css 的相对位置。

功能
按食谱、中文材料、配方条件搜索。
筛选联机版、单机及DLC、肉类、非肉类、角色可食用、特殊用途、锅具。
按生命、饥饿、理智即时恢复、生命与理智累计恢复、保鲜天数、烹饪时间、优先级升降序排序。
点击卡片查看全部示例、材料对照、特殊效果、原图分辨率及对应Wiki详情。
默认显示81条联机版记录，所有版本共139条。

数据范围
基于 dontstarve.wiki.gg 的 Dishes、普通烹饪锅与 Portable Crock Pot（含DST子页）目录逐项读取详情。
共101个英文成品名称，139条版本化记录。龙虾料理的 Lobster / Wobster 是不同版本命名。
81条适用于DST，另58条为单机及DLC版本；南瓜饼干为通用记录，可在单机筛选中同时看到。
普通锅、沃利专属便携锅、失败料理及特殊用途锅内成品均收录。
不含活动专用锅具或暴食活动菜肴、调味料、模组料理、原始食材以及商店购买食物。
本图鉴列出完整最低条件和禁用条件；四格示例并不穷举所有可行排列。

参数与配方口径
三项参数为满新鲜度、标准角色的即时基础值。不同角色偏好、技能、新鲜度、调味与其他状态会改变实际值。
雷根糖：即时生命2 + 2分钟持续恢复120，每锅3份。
舒缓茶：即时理智15 + 1分钟持续恢复30。
牛奶帽：装备使用4分钟累计恢复187.5饥饿，理智约-5.32；并非直接食用的料理。
皮弗娄牛零食、蒸树枝、尘土块不是角色食物，三项角色值不适用，不会参与最高恢复排名。
“肉类”按成品游戏食物类型判断，例如素食堡和果冻沙拉依然属于肉类。
“肉度”“鱼度”等是全锅四种食材贡献的属性总量，不等同于食材数量。同一食材可能贡献多个属性。
必需食材也贡献这些属性，不要把总属性要求机械理解为还需额外添加同样数量的材料。
配方条件同时成立时，先比较优先级；同最高优先级可能随机产出。示例中存在随机结果的已标记。
资料以单项Wiki详情优先于总表。部分Wiki图示为方便展示使用离散最小材料值，已转换为中文条件。
芦笋冷汤的温度效果在来源总表和详情页分别标为40°和20°，保留差异提示。
食谱烹饪时间为页面标称时间，DST沃利便携锅有20%加速，不保证与实际等待时间相同。

图片说明
Wiki网页文本可读取，但图片地址在本次环境返回403；图片使用公开可访问的游戏原始素材镜像。
所有成品及展示的示例食材均有本地图片。6种成品使用128px以上的原生较大尺寸资源，其余多数为64×64原生图标。
不将插值放大或AI重绘冒充原生高清。图片可在HTML中直接打开；来源、尺寸见image_sources.json和单项详情。
分类图标使用代表食材示意，生熟组合材料组通常以生食材表示；具体生熟限制以中文配方条件为准。
填充物以“填”字说明图标表示，不是固定食材。
未收录无可靠本地图片的可选示例（背鳍、干必忘我、营养砖），不影响每个食谱至少一组完整四格示例。

Excel说明
食谱数据：可筛选排序的139行结构化记录，数字列保留为数值。
食谱图文：按固定ID展示成品与一组四格材料示例及中文名字。
材料图鉴：中文名称、英文对应、图片、用途说明、原生尺寸及图片来源。
需要排序时使用“食谱数据”；图片页按ID固定排列，避免排序浮动图片造成错位。

来源与署名
https://dontstarve.wiki.gg/wiki/Crock_Pot
https://dontstarve.wiki.gg/wiki/Crock_Pot/DST
https://dontstarve.wiki.gg/wiki/Dishes
https://dontstarve.wiki.gg/wiki/Portable_Crock_Pot
https://dontstarve.wiki.gg/wiki/Portable_Crock_Pot/DST
各条记录中的source链接对应单项详情页。
中文术语参考Wiki中文页面并进行简体统一和同义名整理；配方数值以英文详情页为主。
https://dontstarve.wiki.gg/zh/wiki/烹飪鍋?variant=zh-cn
https://dontstarve.wiki.gg/zh/wiki/Doc/scripts/preparedfoods.lua?variant=zh-cn
后者仅用于中文名称映射，不用作配方规则来源。

公开图片镜像
Wiki所链接的Food Guide：https://bluehexagons.github.io/foodguide/
项目：https://github.com/bluehexagons/foodguide
补充项目：https://github.com/bostwiek/dontstarvetogether-crockpot
具体图片地址记录在image_sources.json；下载资源在assets目录。

许可
Don't Starve游戏、美术、图片与商标属于Klei Entertainment。
Wiki页面内容按站点声明适用CC BY-SA 4.0，除非另有说明。本图鉴的Wiki整理文本与事实组合按同样许可分享，保留来源链接。
https://creativecommons.org/licenses/by-sa/4.0/
Food Guide镜像的许可证随包保存为IMAGE_LICENSE.txt；游戏美术本身并非该项目的Apache许可证授权范围。
