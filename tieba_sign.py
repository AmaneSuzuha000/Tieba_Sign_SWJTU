from DrissionPage import ChromiumOptions, ChromiumPage
import json
import os
import shutil
import time
import requests
import random
from bs4 import BeautifulSoup

def read_cookie():
    """读取 cookie，优先从环境变量读取"""
    if "TIEBA_COOKIES" in os.environ:
        return json.loads(os.environ["TIEBA_COOKIES"])
    else:
        print("贴吧Cookie未配置！详细请参考教程！")
        return []

def get_level_exp(page):
    """获取等级和经验"""
    try:
        level_ele = page.ele('xpath://*[@id="pagelet_aside/pagelet/my_tieba"]/div/div[1]/div[3]/div[1]/a/div[2]').text
        level = level_ele if level_ele else "未知"
    except:
        level = "未知"
    try:
        exp_ele = page.ele('xpath://*[@id="pagelet_aside/pagelet/my_tieba"]/div/div[1]/div[3]/div[2]/a/div[2]/span[1]').text
        exp = exp_ele if exp_ele else "未知"
    except:
        exp = "未知"
    return level, exp

class TiebaReplyApi:
    """贴吧纯接口回复工具，独立无耦合，复用原签到Cookie"""
    def __init__(self, cookies):
        self.base_url = "https://tieba.baidu.com"
        self.session = requests.Session()
        # 转换DrissionPage Cookie格式为requests可用
        cookie_dict = {c['name']: c['value'] for c in cookies if 'name' in c and 'value' in c}
        self.session.cookies.update(cookie_dict)
        # 贴吧接口通用请求头
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Referer': self.base_url,
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'X-Requested-With': 'XMLHttpRequest'
        }

    def get_tbs(self):
        """获取接口必备tbs参数，带异常处理"""
        try:
            resp = self.session.get(f"{self.base_url}/dc/common/tbs", headers=self.headers, timeout=10)
            return resp.json().get('tbs', '')
        except Exception as e:
            print(f"【接口异常】获取tbs失败：{str(e)[:50]}")
            return ''

    def get_fid(self, forum_name):
        """获取贴吧fid参数"""
        try:
            resp = self.session.get(f"{self.base_url}/f?kw={forum_name}", headers=self.headers, timeout=10)
            soup = BeautifulSoup(resp.text, 'html.parser')
            fid_ele = soup.find('input', {'name': 'fid'})
            return fid_ele.get('value', '') if fid_ele else ''
        except Exception as e:
            print(f"【接口异常】获取{forum_name}吧fid失败：{str(e)[:50]}")
            return ''

    def reply_single(self, forum_name, tid, content):
        """单条回复接口，返回成功/失败详情"""
        tbs = self.get_tbs()
        fid = self.get_fid(forum_name)
        # 核心参数校验
        if not tbs or not fid:
            return {"status": "失败", "reason": "tbs/fid参数获取失败"}
        if not tid or not content:
            return {"status": "失败", "reason": "帖子ID/回复内容不能为空"}

        # 回复请求数据
        data = {
            'kw': forum_name,
            'fid': fid,
            'tid': tid,
            'content': content,
            'anonymous': '0',
            'tbs': tbs,
            'ie': 'utf-8'
        }

        try:
            resp = self.session.post(f"{self.base_url}/f/commit/post/add", 
                                    data=data, headers=self.headers, timeout=15)
            res_json = resp.json()
            if res_json.get('no') == 0:
                return {"status": "成功", "reason": "回复提交成功"}
            else:
                return {"status": "失败", "reason": res_json.get('error', '贴吧接口返回未知错误')}
        except Exception as e:
            return {"status": "失败", "reason": f"请求异常：{str(e)[:50]}"}

    def loop_reply(self, forum_name, tid, content, count=4):
        """回复指定帖子"""
        print(f"\n===== 开始循环回复【{forum_name}吧】帖子ID：{tid}，共{count}次 =====")
        total_success = 0
        for i in range(1, count+1):
            res = self.reply_single(forum_name, tid, content)
            print(f"第{i}次回复：{res['status']} | {res['reason']}")
            if res['status'] == "成功":
                total_success += 1
            # 随机间隔3-8秒，规避贴吧风控
            time.sleep(random.randint(3, 8))
        print(f"===== 回复任务结束，总计成功{total_success}次，失败{count-total_success}次 =====\n")
        return total_success

if __name__ == "__main__":
    print("程序开始运行")
    notice = ''
    co = ChromiumOptions().headless()
    chromium_path = shutil.which("chromium-browser")
    if chromium_path:
        co.set_browser_path(chromium_path)

    page = ChromiumPage(co)
    url = "https://tieba.baidu.com/"
    page.get(url)
    cookies = read_cookie()
    page.set.cookies(cookies)
    page.refresh()
    page._wait_loaded(15)

    over = False
    yeshu = 0
    count = 0

    while not over:
        yeshu += 1
        page.get(f"https://tieba.baidu.com/i/i/forum?&pn={yeshu}")
        page._wait_loaded(15)

        for i in range(1, 22):
            element = page.ele(
                f'xpath://*[@id="like_pagelet"]/div[1]/div[1]/table/tbody/tr[{i}]/td[1]/a/@href'
            )
            try:
                tieba_url = element.attr("href")
                name = element.attr("title")
            except:
                msg = f"全部爬取完成！本次总共签到 {count} 个吧..."
                print(msg)
                notice += msg + '\n\n'
                page.close()
                over = True
                break

            page.get(tieba_url)
            page.wait.eles_loaded('xpath://*[@id="signstar_wrapper"]/a/span[1]',timeout=30)

            # 判断是否签到
            is_sign_ele = page.ele('xpath://*[@id="signstar_wrapper"]/a/span[1]')
            is_sign = is_sign_ele.text if is_sign_ele else ""
            if is_sign.startswith("连续"):
                level, exp = get_level_exp(page)
                msg = f"{name}吧：已签到过！等级：{level}，经验：{exp}"
                print(msg)
                notice += msg + '\n\n'
                print("-------------------------------------------------")
            else:
                page.wait.eles_loaded('xpath://a[@class="j_signbtn sign_btn_bright j_cansign"]',timeout=30)
                sign_ele = page.ele('xpath://a[@class="j_signbtn sign_btn_bright j_cansign"]')
                if sign_ele:
                    sign_ele.click()
                    time.sleep(1)  # 等待签到动作完成
                    sign_ele.click()
                    time.sleep(1)  # 等待签到动作完成
                    page.refresh()
                    page._wait_loaded(15)
                    level, exp = get_level_exp(page)
                    msg = f"{name}吧：成功！等级：{level}，经验：{exp}"
                    print(msg)
                    notice += msg + '\n\n'
                    print("-------------------------------------------------")
                else:
                     msg = f"错误！{name}吧：找不到签到按钮，可能页面结构变了"
                     print(msg)
                     notice += msg + '\n\n'
                     print("-------------------------------------------------")
            count += 1
            page.back()
            page._wait_loaded(10)
     # ===================== 核心配置区=====================
     TARGET_FORUM = "西南交通大学"  # 目标贴吧名（例：轨道交通吧 → 填轨道交通，去掉「吧」字）
     TARGET_TID = "9983496041"  # 目标帖子ID（例：https://tieba.baidu.com/p/1234567890 → 填1234567890）
     REPLY_CONTENT = "3"        # 要回复的内容（自定义，如3、打卡等）
     # ==========================================================================
     # 调用接口回复功能
     if TARGET_FORUM and TARGET_TID and REPLY_CONTENT:
         tieba_api = TiebaReplyApi(cookies)
         success_num = tieba_api.loop_reply(TARGET_FORUM, TARGET_TID, REPLY_CONTENT)
         # 将回复结果加入通知，Server酱会同步推送
         notice += f"\n指定帖子回复结果：【{TARGET_FORUM}吧】ID{TARGET_TID}，共4次，成功{success_num}次，失败{4-success_num}次"
     else:
         print("未正确配置回复参数，跳过回复任务")
         notice += "\n未正确配置回复参数，跳过回复任务"
     # ===================== 原代码：Server酱通知逻辑（完全未改动） =====================
     if "SendKey" in os.environ:
         api = f'https://sc.ftqq.com/{os.environ["SendKey"]}.send'
         title = u"贴吧签到信息"
         data = {
         "text":title,
         "desp":notice
         }
         try:
             req = requests.post(api, data=data, timeout=60)
             if req.status_code == 200:
                 print("Server酱通知发送成功")
             else:
                 print(f"通知失败，状态码：{req.status_code}")
                 print(api)
         except Exception as e:
             print(f"通知发送异常：{e}")
     else:
         print("未配置Server酱服务...")
