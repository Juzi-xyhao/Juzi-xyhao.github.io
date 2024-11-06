---
title: Vector API介绍&简单使用
tags:
  - Java
categories: [Java,新特性,Vector API介绍&简单使用]
author: xyhao
keywords: Vector API是Java用于科学计算的新API
description: Vector API是Java用于科学计算的新API
top_img: 'https://vjs.zencdn.net/v/oceans.mp4'
cover: 'https://vjs.zencdn.net/v/oceans.mp4'
abbrlink: 836246b3
date: 2024-08-02 00:00:00
---

> 更多博客请见 [我的语雀知识库](https://www.yuque.com/u41117719/xd1qgc)  
> > 我在参与腾讯犀牛鸟开源时，认领了有关Vector API的issue。但找遍全网也找不到关于Vector API具体使用的介绍。于是我简单学习Vector API之后写下这篇简单的介绍供大家参考。个人水平有限。不足之处请大家多多指正。
> 
> 【JEP咖啡屋18[熟肉]-如何通过Vector API加速并行计算】[https://www.bilibili.com/video/BV1Nh4y1s7dJ?vd_source=6df57b2b8470f0f2c9187d097a219270](https://www.bilibili.com/video/BV1Nh4y1s7dJ?vd_source=6df57b2b8470f0f2c9187d097a219270)

<a name="x9C3R"></a>
## 介绍
Vector API是自JDK16开始孵化的预览功能，至今仍在孵化中（2024.08.02）。<br />它适用于多个数组的混合运算。将数组转化为多组**定长**的向量进行计算以加快计算速度。而不适用于单数组的内部运算。如：w[i] = w[i - 16] ^ w[i - 9] 
<a name="QW5vV"></a>
## 使用
在使用Vector API中有一个非常重要的概念需要知晓：
<a name="Y0XS5"></a>
### Species
Species是用于确定你的机器能够将几个数组元素转化为向量的关键变量。一般它的长度在64位到512位之间。即可以将2到16个int数组元素转化为一组向量。或者可以将4到32个shortInt数组元素转化为一组向量。<br />Species.length()与机器有关。但我们也可以手动指定。<br />定义一个64位的VectorSpecies物种如下：<br />`private static final VectorSpecies<Integer> SPECIES = IntVector.SPECIES_64;`

<a name="IJQSt"></a>
### 从数组中创建向量
IntVector中提供了一个创建向量的方法fromArray<br />方法签名如下：<br />`IntVector fromArray(VectorSpecies<Integer> species,int[] a, int offset)`

- 创建向量必须根据Species创建
- 从数组a中创建向量
- offset表示从数组第几位开始创建向量
<a name="il9lc"></a>
### 向量写回数组
IntVector中提供了一个写回数组的方法intoArray<br />方法签名：`void intoArray(int[] a, int offset)`<br />
offset表示从数组第几位开始写入。

<a name="sKbf1"></a>
### mask
在标准情况下，并不是每个数组的所有元素都能转化为向量的<br />
前文提到了：Vector API将数组转化为多组**定长**的向量。完全转化需要数组长度能被Species.length整除<br />
但不是每个数组长度都能被Species.length整除<br />

比如数组array = [0, 1, 2, 3, 4.........35]，Species.length = 16。只有前32个元素能够被转化为向量，
剩下的子数组[32, 33, 34, 35]则不能够被转化<br />
在`fromArray`方法内部对offset有检查。如果`offset >= array.length - Species.length`,那么会抛出indexOutOfLength异常。<br />

因此，对于剩下的元素，一般推荐使用原始方式计算。<br />
但`formArray`方法也有一个重载版本可以将剩余元素也转化为向量。<br />重载版本的签名如下<br />
`IntVector fromArray(VectorSpecies<Integer> species,int[] a, int offset,VectorMask<Integer> m)`<br />
多传入一个mask变量，即可做到即使`offset >= array.length - Species.length`，也能转化为向量。但需要`offset < array.length`<br />
mask变量使用示例如下：
```java
/*
    SPECIES.length() = 16
    Array.length = 35
*/
for (int i = 0; i < Array.length; i += SPECIES.length()) {
  var mask = SPECIES.indexInRange(i, w.length);
  IntVector v = IntVector.fromArray(SPECIES, Array, i - 16, mask);
}
```
在代码`var mask = SPECIES.indexInRange(i, array.length);`中，定义变量的var关键字自JDK10开始引入。它允许你在声明变量时省略其类型，编译器会自动推断出其类型。类似于lambda表达式的无类型参数。

<a name="xV4bn"></a>
### lanwise方法
lanewise直接翻译就是车道交叉。在Vector API中，向量被视为车道，不同向量之间的运算被视为车道交叉。<br />简单的加减乘除，在`jdk.incubator.vector.Vector`类中已经封装了。<br />例如：
```java
var va = IntVector.fromArray(SPECIES, a, i);
var vb = IntVector.fromArray(SPECIES, b, i);
var vc = va.add(vb);
vc.intoArray(c, i);
```

### reducesLanes方法
这是一种归约操作，将向量中各个元素通过某种操作组合起来。如计算一组元素的乘积，总和，最大值，最小值等等

以下为计算一组元素的平方和的代码
```java
IntVector v = IntVector.fromArray(IVectorSpecies.SPECIES_128, new int[]{1, 2, 3, 4});
var v2 = v.mult(v);
int sum = v2.reduceLanes(VectorOperators.ADD);
```


### 更加复杂的操作
我们应该如何对向量进行复杂的操作呢？<br />在`jdk.incubator.vector.VectorOperators`中已经定义了很多常用的操作，与或非、异或、同或等等<br />在向量A的lanewise方法中，传入运算符的定义与另一个向量B。即可让A与B执行特定的运算。如<br />`IntVector temp = wPrev16.lanewise(VectorOperators.XOR, wPrev9)`<br />向量temp是 wPrev16和wPrev9的异或运算结果。



<a name="ZdbWo"></a>
## 如何编译运行使用了Vector API的代码？
由于Vector API至今仍处于孵化期，直接使用必然报错。需要在编译时指定两个参数`--enable-preview`和`--add-modules=jdk.incubator.vector`。<br />在哪里指定？<br />网络上一些博客说的在pom文件中添加编译参数：
```xml
<build>
        <plugins>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-compiler-plugin</artifactId>
                <configuration>
                    <compilerArgs>
                        <arg>--enable-preview</arg>
                        <arg>--add-modules=jdk.incubator.vector</arg>
                    </compilerArgs>
                    <compilerVersion>21</compilerVersion>
                    <source>21</source>
                    <target>21</target>
                </configuration>
            </plugin>
        </plugins>

    </build>
```
对我而言并没有用。<br />在IDEA的运行配置中添加也没有用：<br />![image.png](http://121.36.193.119/api/file/getBlogImage?imagePath=assets/articleSource/2024-08-02-VectorAPI/img_1.png)<br /><br />
于是我只能使用最原始的办法。在命令行中运行<br /><br />![image.png](http://121.36.193.119/api/file/getBlogImage?imagePath=assets/articleSource/2024-08-02-VectorAPI/img_2.png)![img.png](http://121.36.193.119/api/file/getBlogImage?imagePath=assets/articleSource/2024-08-02-VectorAPI/img_3.png)<br /><br />
我的机器上的JDK版本是21。想使用Vector API最低也要JDK16。<br /><br />



