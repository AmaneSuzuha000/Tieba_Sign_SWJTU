from DrissionPage import ChromiumOptions, ChromiumPage
import json
import os
import shutil
import time
import requests

def read_cookie():
    """读取 cookie，优先从环境变量读取"""
    if "TIEBA_COOKIES" in os.environ:
        try:
            return json.loads(os.environ["TIEBA_COOKIES"])
        except Exception as e:
            print(f"Cookie解析失败：{e}")
            return []
    else:
        print("贴吧Cookie未配置！详细请参考教程！")
        return []

def get_level_exp(page):
    """获取等级和经验，兼容不同页面结构"""
    level, exp = "未知", "未知"
    # 兼容新老页面xpath，提高容错
    level_eles = [
        '//*[@id="pagelet_aside/pagelet/my_tieba"]/div/div[1]/div[3]/div[1]/a/div[2]',
        '//div[contains(@class,"user-level")]/span'
    ]
    exp_eles = [
        '//*[@id="pagelet_aside/pagelet/my_tieba"]/div/div[1]/div[3]/div[2]/a/div[2]/span[1]',
        '//div[contains(@class,"user-exp")]/span[1]'
    ]
    for ele_xpath in level_eles:
        try:
            level_ele = page.ele(xpath=ele_xpath)
            if level_ele:
                level = level_ele.text.strip()
                break
        except:
            continue
    for ele_xpath in exp_eles:
        try:
            exp_ele = page.ele(xpath=ele_xpath)
            if exp_ele:
                exp = exp_ele.text.strip()
                break
        except:
            continue
    return level, exp

if __name__ == "__main__":
    print("程序开始运行")
    notice = ''
    co = ChromiumOptions().headless()  # 无头模式，后台运行

    # 适配不同系统浏览器路径
    chromium_path = shutil.which("chromium-browser") or shutil.which("chrome") or shutil.which("msedge")
    if chromium_path:
        co.set_browser_path(chromium_path)

    page = ChromiumPage(co)
    url = "https://tieba.baidu.com/"
    
    # 登录核心流程：先访问再设cookie，避免失效
    page.get(url)
    cookies = read_cookie()
    if cookies:
        page.set.cookies(cookies)
        page.refresh()
    page.wait.loaded(timeout=15)  # 替换废弃的_wait_loaded

    over = False
    yeshu = 0
    count = 0

    while not over:
        yeshu += 1
        forum_url = f"https://tieba.baidu.com/i/i/forum?pn={yeshu}"
        page.get(forum_url)
        page.wait.loaded(timeout=15)

        # 循环范围改为1-20（原2-21会漏第一个），兼容分页数量不足情况
        for i in range(1, 21):
            # 优化贴吧链接定位，提高稳定性
            ele_xpath = f'//*[@id="like_pagelet"]/div[1]/div[1]/table/tbody/tr[{i}]/td[1]/a'
            element = page.ele(xpath=ele_xpath)
            if not element:  # 无元素说明本页爬完，直接下一页
                break

            try:
                tieba_url = element.attr("href")
                name = element.attr("title").strip() if element.attr("title") else f"未知贴吧{i}"
                if not tieba_url.startswith("http"):
                    tieba_url = f"https://tieba.baidu.com{tieba_url}"
            except Exception as e:
                print(f"获取贴吧链接失败：{e}")
                continue

            try:
                page.get(tieba_url)
                page.wait.loaded(timeout=20)

                # 签到状态判断（兼容已签到/未签到/异常状态）
                sign_wrapper = page.ele(xpath='//*[@id="signstar_wrapper"]/a/span[1]', timeout=10)
                if not sign_wrapper:
                    msg = f"{name}吧：页面无签到模块，跳过"
                    print(msg)
                    notice += msg + '\n\n'
                    count +=1
                    page.back()
                    time.sleep(0.5)  # 降低访问频率，避免风控
                    print("-------------------------------------------------")
                    continue

                is_sign_text = sign_wrapper.text.strip()
                # 已签到判断（包含"连续""已签到"等关键词）
                if any(key in is_sign_text for key in ["连续", "已签到", "天"]):
                    level, exp = get_level_exp(page)
                    msg = f"{name}吧：已签到！等级：{level}，经验：{exp}"
                    print(msg)
                    notice += msg + '\n\n'
                else:  # 未签到，执行签到
                    sign_btn = page.ele(xpath='//a[contains(@class,"j_signbtn") and contains(@class,"j_cansign")]', timeout=10)
                    if sign_btn:
                        sign_btn.click()
                        time.sleep(1.5)  # 延长等待，确保签到请求发送
                        page.refresh()
                        page.wait.loaded(timeout=10)
                        # 签到后校验
                        new_sign_text = page.ele('//*[@id="signstar_wrapper"]/a/span[1]').text.strip()
                        level, exp = get_level_exp(page)
                        if any(key in new_sign_text for key in ["连续", "已签到"]):
                            msg = f"{name}吧：签到成功！等级：{level}，经验：{exp}"
                        else:
                            msg = f"{name}吧：签到触发验证，需手动处理！"
                    else:
                        msg = f"{name}吧：无可用签到按钮（可能需验证/权限不足）"
                    print(msg)
                    notice += msg + '\n\n'
                
                count +=1
                page.back()
                page.wait.loaded(timeout=10)
                time.sleep(0.5)  # 防反爬
                print("-------------------------------------------------")
            except Exception as e:
                msg = f"{name}吧：签到异常 - {str(e)}"
                print(msg)
                notice += msg + '\n\n'
                count +=1
                page.back()
                time.sleep(1)
                print("-------------------------------------------------")
                continue

        # 分页判断：本页不足20个，说明已爬完所有贴吧
        if i < 19:
            over = True
            msg = f"全部爬取完成！本次共处理 {count} 个吧"
            print(msg)
            notice += msg + '\n\n'

    page.quit()  # 彻底关闭浏览器，释放资源

    # Server酱通知（保持原逻辑）
    if "SendKey" in os.environ:
        api = f'https://sc.ftqq.com/{os.environ["SendKey"]}.send'
        title = "贴吧签到信息"
        data = {"text": title, "desp": notice}
        try:
            req = requests.post(api, data=data, timeout=60)
            if req.status_code == 200:
                print("Server酱通知发送成功")
            else:
                print(f"通知失败，状态码：{req.status_code}")
        except Exception as e:
            print(f"通知发送异常：{e}")
    else:
        print("未配置Server酱服务，跳过通知")
