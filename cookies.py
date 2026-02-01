from DrissionPage import ChromiumPage, ChromiumOptions
import json
import os

co = ChromiumOptions()
chromium_path = os.path.exists("C:/Program Files/Google/Chrome/Application/chrome.exe") or \
                os.path.exists("/usr/bin/chromium-browser") or \
                os.path.exists("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
if chromium_path:
    co.set_browser_path(chromium_path)

page = ChromiumPage(co)
url = 'https://tieba.baidu.com/'

# 保存cookie
def get_cookie():
    try:
        page.get(url)
        print("已打开贴吧首页，请在浏览器中完成登录（扫码/账号密码均可）")
        input('登录成功后按回车继续导出Cookie...')
        
        # 获取cookie
        cookies_list = page.cookies(all_info=True)
        print('共拿到 {} 条 cookie'.format(len(cookies_list)))
        
        # 保存到本地（utf-8编码，防止中文乱码）
        with open('tieba_cookies.json', 'w', encoding='utf-8') as f:
            json.dump(cookies_list, f, ensure_ascii=False, indent=2)
        
        print('Cookie已成功写入 tieba_cookies.json 文件！')
        print('提示：将该文件放签到脚本同目录，或配置环境变量即可使用')
        
    except Exception as e:
        print(f'获取Cookie失败：{str(e)}')
    finally:
        page.quit()  # 自动关闭浏览器

if __name__ == '__main__':
    get_cookie()
