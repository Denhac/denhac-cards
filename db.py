from pywinauto.application import Application, ProcessNotFoundError
import subprocess
import time

windsx_db_path = "C:/WinDSX/DB.exe"

def open_windsx():
	subprocess.Popen([windsx_db_path])
	time.sleep(5)

def get_windsx_app():
	app = None
	attempts = 0
	TOTAL_ATTEMPTS = 5
	while app is None:
		try:
			attempts = attempts+1
			app = Application().connect(path=windsx_db_path)
		except ProcessNotFoundError:
			attempts_remaining = TOTAL_ATTEMPTS - attempts
			print(f"Failed to connect to WinDSX, trying to open, {attempts_remaining} attempt(s) remaining...")
			open_windsx()
			
			if attempts == TOTAL_ATTEMPTS:
				raise

	return app
			

def login_and_close_windsx():
	app = get_windsx_app()
		
	app.Login.Edit0.set_edit_text("master")
	app.Login.OK.click()
	time.sleep(10)
	app.Database.close(5)

def main():
	login_and_close_windsx()
	open_windsx()

main()