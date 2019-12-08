from selenium import webdriver


def has_digits(input_str):
    return any(char.isdigit() for char in input_str)


def start_headless_driver():
    options = webdriver.ChromeOptions()
    options.add_argument('headless')
    driver_path = '/Users/bryangalindo/PycharmProjects/raileggs_beta/raileggs/chromedriver'
    return webdriver.Chrome(executable_path=driver_path, options=options)