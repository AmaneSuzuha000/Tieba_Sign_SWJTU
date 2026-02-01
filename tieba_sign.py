from DrissionPage import ChromiumOptions, ChromiumPage
import json
import os
import shutil
import time
import requests

def read_cookie():
    """读取 cookie，优先从环境变量读取"""
    if "TIEBA_COOKIES" in os.environ:
        return json.loads(os.environ["TIEBA_COOKIES"])
    else:
        print("贴吧Cookie未配置！详细请参考教程！")
        return []

def get_level_exp(page):
    """获取等级和经验，如果找不到返回'未知'"""
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

def send_tieba_comment(page, post_url, comment_content):
    """
    贴吧指定帖子发评论（保留你的核心逻辑）
    page: 浏览器页面对象
    post_url: 目标帖子完整链接
    comment_content: 要发送的评论内容
    return: 评论结果消息
    """
    try:
        # 打开目标帖子
        page.get(post_url)
        page._wait_loaded(15)
        time.sleep(1)  # 缓冲加载

        # 1. 定位评论输入框
        comment_input = page.ele(xpath='//textarea[@id="ueditor_replace"]', timeout=10)
        if not comment_input:
            comment_input = page.ele(xpath='//textarea[contains(@class,"comment-input")]', timeout=5)
        if not comment_input:
            return "失败：未找到评论输入框（页面结构可能更新）"

        # 2. 清空+输入评论内容（新增clear，避免残留内容）
        comment_input.clear()
        comment_input.input(comment_content)
        time.sleep(0.8)  # 避免输入过快

        # 3. 定位并点击发送按钮
        send_btn = page.ele(xpath='//button[contains(text(),"发表")]', timeout=10)
        if not send_btn:
            send_btn = page.ele(xpath='//input[@value="发表回复" or @value="发表评论"]', timeout=5)
        if not send_btn:
            return "失败：未找到发表按钮"

        send_btn.click()
        time.sleep(2)  # 等待发送请求完成

        # 4. 校验是否发送成功（判断提示）
        success_msg = page.ele(xpath='//div[contains(text(),"回复成功") or contains(text(),"评论成功")]', timeout=5)
        error_msg = page.ele(xpath='//div[contains(text(),"失败") or contains(text(),"请登录") or contains(text(),"违规")]', timeout=3)
        
        if success_msg:
            return f"成功：评论已发送，内容【{comment_content}】"
        elif error_msg:
            return f"失败：{error_msg.text.strip()}"
        else:
            return "成功：评论提交（无明确提示，大概率发送成功）"

    except Exception as e:
        return f"异常失败：{str(e)}"

if __name__ == "__main__":
    print("程序开始运行")

    # 通知信息
    notice = ''


    co = ChromiumOptions().headless()
    chromium_path = shutil.which("chromium-browser")
    if chromium_path:
        co.set_browser_path(chromium_path)

    page = ChromiumPage(co)

    url = "https://tieba.baidu.com/"
    page.get(url)
    page.set.cookies(read_cookie())
    page.refresh()
    page._wait_loaded(15)


    over = False
    yeshu = 0
    count = 0

    while not over:
        yeshu += 1
        page.get(f"https://tieba.baidu.com/i/i/forum?&pn={yeshu}")

        page._wait_loaded(15)

        for i in range(2, 22):
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

    #指定帖子评论+3
    target_post_url = "https://tieba.baidu.com/p/9983496041"  # 你的目标帖子链接
    my_comment = "3"  # 你的指定评论内容
    if cookies:  # 有cookie才执行（避免未登录）
        # 重新打开浏览器发评论（原浏览器已关闭）
        comment_page = ChromiumPage(co)
        comment_page.get("https://tieba.baidu.com/")
        comment_page.set.cookies(cookies)
        comment_page.refresh()
        # 调用评论函数
        for i in range(1, 5):  # 1-4 共4次
             print(f"执行第{i}次评论")
             comment_result = send_tieba_comment(comment_page, target_post_url, my_comment)
             print(f"第{i}次评论结果：{comment_result}")
             notice += f"第{i}次：{comment_result}\n"
             # 间隔8秒，避免被风控（最后1次不用等）
             if i < 4:
                 time.sleep(8) 
             comment_page.quit()  # 关闭评论专用浏览器
    else:
        no_comment_msg = "未执行评论：Cookie未配置/未登录"
        print(no_comment_msg)
        notice += f"\n{no_comment_msg}"


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
