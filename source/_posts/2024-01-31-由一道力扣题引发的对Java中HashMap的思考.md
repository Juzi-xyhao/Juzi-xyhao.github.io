---
title: 2024-01-31-由一道力扣题引发的对Java中HashMap的思考
tags:
  - Java
  - HashMap
categories: [Java,HashMap,由一道力扣题引发的对Java中HashMap的思考]
author: xyhao
keywords: 开始背JUC八股的起点
description: 开始背JUC八股的起点
top_img: >-
  https://gitee.com/xyhaooo/picrepo/raw/master/assets/articleCover/2024-01-31-Hash.png
cover: >-
  https://gitee.com/xyhaooo/picrepo/raw/master/assets/articleCover/2024-01-31-Hash.png
comments: true
abbrlink: 422bd100
date: 2024-01-31 00:00:00
updated: 2024-02-01 00:00:00
toc:
toc_number:
toc_style_simple:
copyright:
copyright_author:
copyright_author_href:
copyright_url:
copyright_info:
---

> 更多博客请见 [我的语雀知识库](https://www.yuque.com/u41117719/xd1qgc)

<br>

哈希表插入是在尾节点插入，因为需要遍历哈希桶内所有链表节点判断重复

哈希表的底层是由数组、链表和红黑树实现的，数组作为哈希桶。<br />桶内的结点个数小于8链表实现，大于等于8红黑树实现<br />Java中所有类都继承了Object类，该类中有一个hashCode方法，是C++实现的native方法，将key的内存地址转化为32位int数a，再对a右移16位得到b，将a与b异或得到c作为key的哈希值。得到的哈希值对哈希桶长度 - 1做&操作，结果就是key要被放入的桶的索引。如果这个结果超过了哈希桶长度，那么就会生成一个新的哈希桶。
```java
//本方法在Objects.java文件内
public native int hashCode();

static final int hash(Object key) {
    int h;
    return (key == null) ? 0 : (h = key.hashCode()) ^ (h >>> 16);
}

public V put(K key, V value) {
    return putVal(hash(key), key, value, false, true);
}

/**
* Implements Map.put and related methods.
*
* @param hash hash for key
* @param key the key
* @param value the value to put
* @param onlyIfAbsent if true, don't change existing value
* @param evict if false, the table is in creation mode.
* @return previous value, or null if none
*/
final V putVal(int hash, K key, V value, boolean onlyIfAbsent,
                   boolean evict) {
    Node<K,V>[] tab; Node<K,V> p; int n, i;
    // table未初始化或者长度为0，进行扩容
    if ((tab = table) == null || (n = tab.length) == 0)
        n = (tab = resize()).length;
    // (n - 1) & hash 确定元素存放在哪个桶中，桶为空，新生成结点放入桶中(此时，这个结点是放在数组中)
    if ((p = tab[i = (n - 1) & hash]) == null)
        tab[i] = newNode(hash, key, value, null);
    // 桶中已经存在元素（处理hash冲突）
    else {
        Node<K,V> e; K k;
        //快速判断第一个节点table[i]的key是否与插入的key一样，若相同就直接使用插入的值p替换掉旧的值e。
        if (p.hash == hash &&
            ((k = p.key) == key || (key != null && key.equals(k))))
                e = p;
        // 判断插入的是否是红黑树节点
        else if (p instanceof TreeNode)
            // 放入树中
            e = ((TreeNode<K,V>)p).putTreeVal(this, tab, hash, key, value);
        // 不是红黑树节点则说明为链表结点
        else {
            // 在链表最末插入结点
            for (int binCount = 0; ; ++binCount) {
                // 到达链表的尾部
                if ((e = p.next) == null) {
                    // 在尾部插入新结点
                    p.next = newNode(hash, key, value, null);
                    // 结点数量达到阈值(默认为 8 )，执行 treeifyBin 方法
                    // 这个方法会根据 HashMap 数组来决定是否转换为红黑树。
                    // 只有当数组长度大于或者等于 64 的情况下，才会执行转换红黑树操作，以减少搜索时间。否则，就是只是对数组扩容。
                    if (binCount >= TREEIFY_THRESHOLD - 1) // -1 for 1st
                        treeifyBin(tab, hash);
                    // 跳出循环
                    break;
                }
                // 判断链表中结点的key值与插入的元素的key值是否相等
                if (e.hash == hash &&
                    ((k = e.key) == key || (key != null && key.equals(k))))
                    // 相等，跳出循环
                    break;
                // 用于遍历桶中的链表，与前面的e = p.next组合，可以遍历链表
                p = e;
            }
        }
        // 表示在桶中找到key值、hash值与插入元素相等的结点
        if (e != null) {
            // 记录e的value
            V oldValue = e.value;
            // onlyIfAbsent为false或者旧值为null
            if (!onlyIfAbsent || oldValue == null)
                //用新值替换旧值
                e.value = value;
            // 访问后回调
            afterNodeAccess(e);
            // 返回旧值
            return oldValue;
        }
    }
    // 结构性修改
    ++modCount;
    // 实际大小大于阈值则扩容
    if (++size > threshold)
        resize();
    // 插入后回调
    afterNodeInsertion(evict);
    return null;
}
```

![](https://gitee.com/xyhaooo/picrepo/raw/master/assets/articleSource/2024-01-31-HashMap/img.png)<br />
可以看到，在执行putVal方法之前，会调用native方法hashCode得到哈希值，由于这个方法会让每一个不同的对象都得到不同的哈希值，如果我们希望两个内存地址不同但相同内容的数组的哈希值也相等，就必须重写hashCode方法，使得相同内容的数组的哈希值也相等。<br />Java为许多常用的数据类型重写了hashCode()方法,使它们只要内容相同哈希值就也相同，比如String，Integer，Double等。比如在Integer类中哈希值就是其int类型的数据。
```java

public static int hashCode(int value) {
        return value;
    }
```
```java
/**
Returns a hash code based on the contents of the specified array. 
For any two non-null int arrays a and b such that Arrays.equals(a, b), 
it is also the case that Arrays.hashCode(a) == Arrays.hashCode(b).
 */
public static int hashCode(int a[]) {
    if (a == null)
        return 0;
    
    int result = 1;
    for (int element : a)
        result = 31 * result + element;
    
    return result;
}
```
通常重写hashCode方法后还需要重写equals方法。这是因为对象通过调用 Object.hashCode（）生成哈希值，由于不可避免地会存在哈希值冲突的情况 因此hashCode 相同时 还需要再调用 equals 进行一次值的比较，但是若hashCode不同，将直接判定两个对象不同，跳过 equals ，这加快了冲突处理效率。
```java
Node<K,V> e; K k;
            if (p.hash == hash &&
                ((k = p.key) == key || (key != null && key.equals(k))))
                e = p;
//来源于Map.put()方法的底层实现代码的一部分
```
第三行代码中，由于重写了hashCode方法，导致内容相同的数组具有相同的哈希值，于是判断p中的键是否等于传来的数组（比较地址）肯定是不等于的，于是执行key.equals方法。<br />因此，重写hashCode方法导致不同地址的对象具有了相同的哈希值后，为了让某些方法的底层实现将它们作为完全相同的对象，需要重写equals方法。

Object 类定义中对 hashCode和 equals 要求如下:

- **如果两个对象的equals的结果是相等的，则两个对象的 hashCode 的返回结果也必须是相同的。**
- **任何时候重写equals，都必须同时重写hashCode**。




相关链接<br />[源码解读HashMap底层结构与实现原理之一--put、get方法大起底](https://zhuanlan.zhihu.com/p/354863363)<br />[底层原理_森森之火的博客-CSDN博客](https://blog.csdn.net/yb546822612/category_10021000.html)
