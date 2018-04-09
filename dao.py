#coding:utf8
'''
数据连接类,在MySQLdb的基础上进行升级
get_one:获取一条查询记录,接受参数sql语句,返回一个元组
insert:插入一条数据,接受一个字典
'''
import MySQLdb


class dao():
    '''设置数据库连接参数,默认字符集为utf8,参数都是字符串'''
    def __init__(self,host,username,password,dbname,charset='utf8'):
        self.db = MySQLdb.connect(host,username,password,dbname,charset='utf8')
        self.cursor = self.db.cursor()
    '''传入sql语句,返回查询后的结果'''
    def get_one(self,sql):
        try:
            self.cursor.execute(sql)
            record = self.cursor.fetchone()
            return record
        except Exception,e:
            print str(e)
            return False
    '''插入一条数据,data为字典'''
    def insert(self,table_name,data):
        sql = "insert into {}{} values ".format(table_name,tuple(data.keys())).replace("'",'') + str(tuple(data.values()))
        # print sql
        try:
            self.cursor.execute(sql)
            self.db.commit()
            # 返回插入后新增的id
            return int(self.cursor.lastrowid)
        except Exception,e:
            self.db.rollback()
            print str(e)
            return False
    '''更新数据,data是字典,table_name/restriction_str是字符串'''
    def update(self,table_name,data,restriction_str):
        data_str = ''
        for item in data.items():
            data_str += '{}="{}",'.format(item[0], item[1])
        values = data_str[:-1]
        sql = 'update {} set {} where {}'.format(table_name,values,restriction_str)
        # print sql
        try:
            self.cursor.execute(sql)
            self.db.commit()
            return self.cursor.rowcount
        except Exception, e:
            self.db.rollback()
            print str(e)
            return False


if __name__ == "__main__":
    dao = dao('localhost','root','123456','test')
    # myqueue.push('www.duu2.com','deatil','a')
    # myqueue.push('www.duu3.com', 'deatil','b')
    # myqueue.push('www.duuqq.com', 'deatil','b')
    sql = 'select * from download'
    print dao.get_one(sql)
    # data = {"url":"dfhjshddi","name":"baidu","path":"/ajdajsohf/fdsjds"}
    # print dao.insert('download',data)
    a = dao.update('download',{"url":"dfhjshddi","name":"baidu","path":"/ajdajsohf/fdsjds"},'id =1')
    print a