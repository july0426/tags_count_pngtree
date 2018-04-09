#coding:utf-8
'''
采集pngtree的热门tag,并进行统计
数据统计使用redis的有序集(sorted set)类型,插入的值不存在就新增一个值(score=1),存在就给该值的score +1
get_list:循环生成所有的列表页,在每个列表页中采集详情页的url,调用get_detail  (url传递给get_detail)
        循环结束后,把redis数据持久化存储到mysql,并把redis的缓存数据删除
get_detail:采集每张图片的tag,先向MySQL查找指定url的数据,找到了就提取出来,存入redis,更新日期为当日
            未找到url,就发起HTTP请求,采集数据,分别存入redis和MySQL

'''
import urllib,re,socket,redis,gevent,MySQLdb,time
from dao import dao
from lxml import etree
class pngtree():
    # 设置请求超时时间
    socket.setdefaulttimeout(50)
    global mydao
    mydao = dao('localhost', 'root', '123456', 'test')
    # global dao
    def __init__(self,host,cat,sort_rule):
        self.url = 'https://pngtree.com'
        self.cat = cat
        self.date = time.strftime("%d/%m/%Y")
        self.sort_rule = sort_rule
        self.pool = redis.ConnectionPool(host=host, port=6379, decode_responses=True)
        # host是redis主机，需要redis服务端和客户端都起着 redis默认端口是6379
        self.r = redis.Redis(connection_pool=self.pool)
    def get_list(self):
        for i in range(1,201):
            # 拼接成这种的url   https://pngtree.com/free-vectors/193?sort=popular
            if self.cat == 'Recently-Download':
                list_url = 'https://pngtree.com/freepng/{}/{}'.format(self.cat, i)
            else:
                list_url = 'https://pngtree.com/{}/{}?sort={}'.format(self.cat,i,self.sort_rule)
            print list_url
            #从队列中取出一个子类URL
            list_html = self.get_html(list_url)
            if list_html != 0:
                if list_html is not None:
                    urls = list_html.xpath('//*[@id="v2-content"]/div/div[2]/div/ul/li//div//a[@class="tran"]/@href')
                    for url in urls:
                        detail_url = self.url + url
                        print detail_url
                        self.get_detail(detail_url)

        # 处理图片的tag
        tag_key = '{}_{}_{}'.format(self.cat, self.sort_rule, 'tag')
        # 读取tag_key的所有的值和score的数值
        tag_list = self.r.zrange(tag_key, 0, -1, withscores=True, desc=True)
        for i in tag_list:
            tag, count = i
            print tag, count
            # 存入MySQL数据库
            png_test.redis_to_mysql(str(tag), int(count), tag_key)

        # 处理图片的相关的tag
        related_tag_key = '{}_{}_{}'.format(self.cat, self.sort_rule, 'related_tag')
        # 读取related_tag_key的所有的值和score的数值
        related_tag_list = self.r.zrange(related_tag_key, 0, -1, withscores=True, desc=True)
        for i in related_tag_list:
            tag, count = i
            print tag, count
            # 存入mysql数据库
            png_test.redis_to_mysql(str(tag), int(count), related_tag_key)

        # 删除redis的2个key
        self.r.delete(tag_key,related_tag_key)

    def get_detail(self,detail_url):
        sql = 'select tags,related_tags from pngtree_hot_tags where url = "%s"' % detail_url
        # 去mysql  pngtree_hot_tags表中获取tags,获取到就更新日期为今日,未获取就进行HTTP请求抓取tags存入数据库
        tags_saved = mydao.get_one(sql)
        # print tags_saved
        if tags_saved == None or tags_saved == False:
            detail_html = self.get_html(detail_url)
            # 判断是否链接超时，链接超时返回是0
            if detail_html != 0 and detail_html is not None:
                # 获取tags
                tags = detail_html.xpath('//*[@id="v2-details"]/div/div[2]/div[2]//text()')
                # 防止出现404等页面
                if tags:
                    tag_key = '{}_{}_{}'.format(self.cat, self.sort_rule, 'tag')
                    tags_list = []
                    for i in tags:
                        if '\n' not in i:
                            print i
                            if i == '':
                                pass
                            else:
                                i = i.strip()
                                print i
                                # 连接redis
                                tags_list.append(i)
                                self.r.zincrby(tag_key, i)
                    # 把tags列表转换成字符串
                    tags_text = ','.join(tags_list)

                    # 获取related_tags
                related_tags = detail_html.xpath('//*[@id="v2-details"]/div/div/div[4]//text()')
                if related_tags:
                    related_tag_key = '{}_{}_{}'.format(self.cat, self.sort_rule, 'related_tag')
                    related_tags_list = []
                    for i in related_tags:
                        if '\n' not in i:
                            if i == 'Related recommendation:':
                                pass
                            elif i == '':
                                pass
                            else:
                                print i
                                i = i.strip('')
                                print i
                                related_tags_list.append(i)
                                self.r.zincrby(related_tag_key, i)
                    related_tags_text = ','.join(related_tags_list)

                    # 把url,tags存入mysql数据库pngtree_hot_tags表中
                    table_name = 'pngtree_hot_tags'
                    data = {'url': detail_url, 'tags':tags_text,'related_tags':related_tags_text, 'dates': self.date}
                    mydao.insert(table_name, data)

        else:
            # 如果mysql数据库中有相关数据,就读取相关数据,存入redis
            tags = tags_saved[0].split(',')
            tag_key = '{}_{}_{}'.format(self.cat, self.sort_rule, 'tag')
            for i in tags:
                if '\n' not in i:
                    print i
                    if i == '':
                        pass
                    else:
                        self.r.zincrby(tag_key, i)
            related_tags = tags_saved[0].split(',')
            related_tag_key = '{}_{}_{}'.format(self.cat, self.sort_rule, 'related_tag')
            for i in related_tags:
                if '\n' not in i:
                    if i == 'Related recommendation:':
                        pass
                    elif i == '':
                        pass
                    else:
                        print i
                        # 向redis数据库中插入数据   zset
                        self.r.zincrby(related_tag_key, i)
            # 更新数据日期为今日
            restriction_str = 'url="%s"'%detail_url
            mydao.update('pngtree_hot_tags',{'dates':self.date},restriction_str)


    def get_proxy(self):
        sql = "select id,proxy from proxy_google_tag order by status asc limit 1 "
        try:
            # 获取代理
            proxy = mydao.get_one(sql)
            id,proxie = proxy
            # 更新代理时间戳
            mydao.update('',{'status':int(time.time())},'id=%s'%id)
            proxies = {
                'http':'http://%s' % proxie,
                'https':'https://%s' % proxie
            }
        except Exception, e:
            print str(e)
            proxies = ''
        return proxies
    def get_html(self,url):
        try:
            # 加代理
            # proxy = self.get_proxy()
            # if proxy == None or proxy == '':
            #     request = urllib.urlopen(url)
            # else:
            #     request = urllib.urlopen(url,proxies = proxy)
            # 请求URL，获取他的html
            request = urllib.urlopen(url)
            response = request.read()
            html = etree.HTML(response)
            return html
        except Exception as e:
            print str(e)
            print 'fail_url : ',url
            return 0

    def redis_to_mysql(self,tag, count, type_port):
        try:
            data = {'tag': tag, 'count': count, 'type_port': type_port}
            mydao.insert('tag_pngtree_count', data)
        except Exception, e:
            print 'Redis save to MySQL faild...'
            print str(e)



if __name__ == '__main__':
    # 实力化一个类
    png_test = pngtree('localhost','free-vectors','popular')
    png_test.get_list()















    # png_test1 = pngtree('localhost','free-vectors','new')
    # gevent.joinall([
    #     gevent.spawn(png_test.get_list),
    #     gevent.spawn(png_test1.get_list),
    # ])
    # 获取到所有的子类，及url
    # png_test.get_detail('https://pngtree.com/freepng/purple-wedding-invitation-cover_2367994.html')
    # 获取列表页
    # png_test.get_list()
    # 爬取详情页
    # while True:
    #     png_test.get_detail()
    # 如果有失败的，去重新爬取
    # png_test.fail_handler()
    # 如果有处理半路终止的，从新爬取
    # png_test.process_handler()
    # pool = redis.ConnectionPool(host='localhost', port=6379, decode_responses=True, db=0)
    # host是redis主机，需要redis服 务端和客户端都起着 redis默认端口是6379
    # r = redis.Redis(connection_pool=pool)
    # tag_key = 'free-vectors_popular_resolution'
    # tag_list = r.zrange(tag_key, 0, -1, withscores=True, desc=True)
    # for i in tag_list:
    #     print i
    #     tag,count = i
    #     print tag,count
    #     png_test.redis_to_mysql(str(tag),int(count),'free-vectors_popular_resolution')
    #     # redis_to_mysql(str(tag),int(count),'free-vectors_popular_tag')
    # # print r.sort('border1',by='score')
    # # print r.zcount('broder1')
    # print r.zrange('border1',0,-1,withscores=True,desc=True)
    # # print r.zrank()
    # # r.zincrby('border1',1,' border')
    # # r.zincrby('border1',1,' border')
    # # r.zincrby('border1',1,' border')






















