---
title: HTTP&HTTPS&edge&chrome
categories: [其它,HTTP&HTTPS&edge&chrome]
author:  xyhao
keywords: 偶然发现edge调试http类型url被屏蔽时状态码一栏空空如也
description: 偶然发现edge调试http类型url被屏蔽时状态码一栏空空如也？
comments: true
date: 2024-11-06 19:00:00
abbrlink: '0'
top_img: >-
  http://121.36.193.119/api/file/getBlogImage?imagePath=assets/articleCover/2024-11-06-edgechrome.png
cover: >-
  http://121.36.193.119/api/file/getBlogImage?imagePath=assets/articleCover/2024-11-06-edgechrome.png
tags:
  - 其它
---


## 前情提要
原本博客直接部署在github.io上，并白嫖GitHub的免费图床，但访问需要挂梯子，为了更方便地访问，我注册了一个域名并使用免费的cloudflare做CDN分发。  
但这样做确实博客里的文字可以被加载出来，但是图床还是GitHub，不挂梯子图片自然还是加载不出来。
如图：

![](http://121.36.193.119/api/file/getBlogImage?imagePath=assets/articleSource/2024-11-06-edgechrome/img_2.png)  


![](http://121.36.193.119/api/file/getBlogImage?imagePath=assets/articleSource/2024-11-06-edgechrome/img_3.png)


但还好我还有华为云的个人服务器，于是自己简易搭建了一个图床服务器。相关代码在文末给出。

## 状态码：`已屏蔽：mixed-content`
图床建好后修改图片链接，重新访问看看？
发现还是显示上面两张图，图片一张都没加载出来。按理说我的服务器在国内，不可能访问不了，所以我在电脑上打开chrome浏览器开始调试:

![](http://121.36.193.119/api/file/getBlogImage?imagePath=assets/articleSource/2024-11-06-edgechrome/img_1.png)  

原本应该显示状态码的地方显示`已屏蔽：mixed-content` 。  
好嘛，没见过这玩意的八股战士应声倒地。赶紧问问通义：

![](http://121.36.193.119/api/file/getBlogImage?imagePath=assets/articleSource/2024-11-06-edgechrome/img_4.png)   

原来是这些URL全走HTTP协议，但是网站是以HTTPS协议访问的。HTTPS把HTTP给ban了。
问题找出来了，怎么解决呢？
- 以后只以HTTP协议访问
- 给我的服务器装SSL证书，但这样做需要一个域名，我手里唯一的域名juziblog.space已经绑了本站。试试二级域名，发现我为了cloudflare的CDN加速已经修改了DNS解析，如果不改回去二级域名不会生效，改回去cloudflare就不会生效。那就算了吧

![](http://121.36.193.119/api/file/getBlogImage?imagePath=assets/articleSource/2024-11-06-edgechrome/img_5.png)  

之后我鬼使神差地又用edge浏览器调试了一遍，发现edge的调试工具连`已屏蔽：mixed-content`都不报，状态栏那里全是空白？
还好先用chrome调试，不然这个问题不知道得到什么时候才能发现。

![](http://121.36.193.119/api/file/getBlogImage?imagePath=assets/articleSource/2024-11-06-edgechrome/img.png)  


## 图床简易代码
将文件写入HTTP的response即可，记得设置一些HTTP的头部字段
```java
@RestController("fileInfoController")
@RequestMapping("/file")
public class FileInfoController extends CommonFileController {
    // url举例：http://121.36.193.119/api/file/getBlogImage?imagePath=assets/articleCover/2024-01-31-Hash.png
    @RequestMapping("/getBlogImage")
    public void getImage1(HttpServletResponse response,
                          String imagePath) {
        if (StringUtils.isBlank(imagePath)) {
            return;
        }
        String imageSuffix = StringTools.getFileSuffix(imagePath);
        String filePath = appConfig.getProjectFolder() + Constants.FILE_FOLDER_FILE  + "/" + imagePath;
        imageSuffix = imageSuffix.replace(".", "");
        String contentType = "image/" + imageSuffix;
        response.setContentType(contentType);
        response.setHeader("Cache-Control", "max-age=2592000");
        readFile(response, filePath);
    }

    protected void readFile(HttpServletResponse response, String filePath) {
        if (!StringTools.pathIsOk(filePath)) {
            return;
        }
        OutputStream out = null;
        FileInputStream in = null;
        try {
            File file = new File(filePath);
            if (!file.exists()) {
                return;
            }
            in = new FileInputStream(file);
            byte[] byteData = new byte[1024];
            out = response.getOutputStream();
            int len = 0;
            while ((len = in.read(byteData)) != -1) {
                out.write(byteData, 0, len);
            }
            out.flush();
        } catch (Exception e) {
            logger.error("读取文件异常", e);
        } finally {
            if (out != null) {
                try {
                    out.close();
                } catch (IOException e) {
                    logger.error("IO异常", e);
                }
            }
            if (in != null) {
                try {
                    in.close();
                } catch (IOException e) {
                    logger.error("IO异常", e);
                }
            }
        }
    }
}
```


