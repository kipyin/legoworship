---
title: 敬拜安排
layout: page
permalink: /services/
---


### 主日敬拜

{%- assign services = site.data.services | sort: "date" | reverse -%}

{% for service in services %}

#### [{{ service.date }}]({{ site.baseurl }}/services/{{ service.date }}.html)

+ 带领：{{ service.lead_singer }}
{%- if service.vocals %}
+ 伴唱：{{ service.vocals | join: "，"}}
{%- endif %}
{%- if service.instrumentation %}
+ 乐器：
{%- for instrument in service.instrumentation %}
    - {{ instrument.instrument }}：{{ instrument.player }}
{%- endfor -%}
{%- endif %}
+ 曲目：
{%- for song in service.songs -%}
{%- assign this_song = site.data.songs | where: "name", song -%}
{%- if this_song.first.sheet_type -%}
    {%- capture sheet_link -%}
        http://pz2c5nkyy.bkt.clouddn.com/{{ this_song.first.key | url_encode}}-{{ this_song.first.name | url_encode | replace: "+", "%20" }}-{{ this_song.first.sheet_type | url_encode }}.jpg
    {%- endcapture %}
    - [{{ song }}]({{ sheet_link }})
{%- else %}
    - {{ song }}
{%- endif -%}
{%- endfor -%}
{%- endfor %}

### 特别活动

#### 十一营会（2019年10月2日～2019年10月4日）