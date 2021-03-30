from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.keys import Keys
from selenium.webdriver import ActionChains
from tabulate import tabulate
from optparse import OptionParser
import datetime
import math

def human_format(num):
    magnitude = 0
    while abs(num) >= 1000:
        magnitude += 1
        num /= 1000.0
    # add more suffixes if you need them
    return '%.0f%s' % (num, ['', 'K', 'M', 'G', 'T', 'P'][magnitude])

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

options = webdriver.ChromeOptions() 
options.add_argument("--log-level=OFF")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option('useAutomationExtension', False)

def getDriver(url_link, msg):
  driver = webdriver.Chrome(options=options, service_log_path='NUL')
  try:
    driver.get(url_link)
    WebDriverWait(driver, 5)
  except:
    print(f"{bcolors.FAIL}" + msg + f"{bcolors.ENDC}")
    driver.quit()
    exit(-1)
  return driver

def fetch_dividend_data(company_symbol):
  url_nasdqa = "http://www.nasdaq.com/market-activity/stocks/" +  company_symbol + "/dividend-history"
  driver = getDriver(url_nasdqa, "Stock (" +  company_symbol + ") not listed at nasdaq")
  html=driver.page_source
  driver.quit()
  soup = BeautifulSoup(html, 'html.parser')
  eff_date = []

  try:
    div_container = soup.find('tbody', class_='dividend-history__table-body')
    for ptag in div_container.find_all('th', class_='dividend-history__cell'):
        # prints the p tag content
        eff_date.append(ptag.text)
  except:
    print(f"{bcolors.FAIL}Stock (" +  company_symbol + f") not listed at nasdaq{bcolors.ENDC}")
    exit(-1)

  cash_amounts = []
  for ptag in div_container.find_all('td', class_='dividend-history__cell dividend-history__cell--amount'):
      # prints the p tag content
      cash_amounts.append(ptag.text[1:])

  eff_date_do = []
  for d in eff_date:
    d_do = datetime.datetime.strptime(d, '%M/%d/%Y')
    eff_date_do.append(d_do)

  date_cash_dict = dict(zip(eff_date, cash_amounts))

  year_list = []
  for d in eff_date_do:
    year_list.append(d.year)

  max_year = max(year_list)

  div_list = []
  latest_dividend_amount = 0
  for i in range(0,3):
    div_in_year1 = 0
    for d in eff_date_do:
      if d.year == datetime.date(max_year-1-i, 7, 25).year:
        d_str = d.strftime('%M/%d/%Y')
        div_in_year1 = div_in_year1 +  float(date_cash_dict[d_str])
        if i == 0:
          latest_dividend_amount += float(date_cash_dict[d_str])
        #print( d_str + " : " + date_cash_dict[d_str])

    div_in_year2 = 0
    for d in eff_date_do:
      if d.year == datetime.date(max_year-2-i, 7, 25).year:
        d_str = d.strftime('%M/%d/%Y')
        div_in_year2 = div_in_year2 +  float(date_cash_dict[d_str])
        #print( d_str + " : " + date_cash_dict[d_str])

    div_percentage = ((div_in_year1 - div_in_year2) / div_in_year1) * 100
    div_list.append(div_percentage)
    #print("div_percentage for: " + str(max_year-1-i) + "-" + str(max_year-2-i) + ": " + str(div_percentage) + "%")

  div_tot = 0
  for i in div_list:
    div_tot += i

  avg_div = div_tot / len(div_list)
  return [latest_dividend_amount, avg_div]

def fetch_stock_price_date(company_symbol, adjust_stock_price_increase):
  url_mw = "https://www.marketwatch.com/investing/stock/" +  company_symbol + "/analystestimates?mod=mw_quote_tab"
  driver = getDriver(url_mw, "Stock (" +  company_symbol + ") not listed at marketwatch") 
  html = driver.page_source
  driver.quit()

  soup = BeautifulSoup(html, 'lxml')
  company_meta_data = soup.find_all('meta')
  company_name = ""
  for i in company_meta_data:
    if str(i.get('name')) == "name":
      company_name = str(i.get('content'))

  soup = BeautifulSoup(html, 'html.parser')
  stock_tables = soup.find('table', class_='table value-pairs no-heading font--lato')

  current_price = soup.find("script", type="application/ld+json")
  r2 = str(current_price).split(',')
  cur_price = 0
  for p_str in r2:
    if "price" in p_str:
      result = p_str.split(':')
      if result[0] == "\"price\"":
        cur_price = float(result[1][1:-1])
        break 

  avg_target_price = []
  for ptag in stock_tables.find_all('tbody'):
    avg_target_price = ptag.text.splitlines()
  avg_target_price = list(filter(None, avg_target_price))
  avg_stock_price_inc = ((float(avg_target_price[3])-cur_price)/float(cur_price)) * 100
  new_sp_after_adj = avg_stock_price_inc+adjust_stock_price_increase

  return [cur_price, new_sp_after_adj, avg_target_price[3], avg_stock_price_inc, company_name]

def calculate_compound_dividend(invest_amount, cur_price, latest_dividend_amount, avg_div, new_sp_after_adj):
  url_calculator = "https://www.buyupside.com/calculators/dividendreinvestmentdec07.htm"
  driver = getDriver(url_calculator, "Dividend calculator not found. Exiting...") 
  no_shares = int(invest_amount/cur_price)

  fieldbackspacedict = [ ["initial_number_shares", 3 , no_shares],
                         ["initial_price_pershare", 3, cur_price],
                         ["annual_dividend", 1, latest_dividend_amount],
                         ["dividend_growthrate", 1, avg_div],
                         ["valuepershare_growthrate", 1, new_sp_after_adj]
                       ]

  for field in fieldbackspacedict:
    inputElement = driver.find_element_by_name(field[0])
    for i in range(0,field[1]):
      inputElement.send_keys(Keys.BACKSPACE)
    inputElement.send_keys(str(field[2]))

  result_list = [["Years of\nInvestment", "Total\nValue", "    New\nShares Added", "Divided\nValue", "Annualized\nReturn"]]

  for years_ in ["05", "10", "15", "20", "25", "30"]:
    inputElement = driver.find_element_by_name("number_years")
    inputElement.send_keys(Keys.BACKSPACE)
    inputElement.send_keys(Keys.BACKSPACE)
    inputElement.send_keys(years_)

    inputElement = driver.find_element_by_name("button")
    ActionChains(driver).click(inputElement).perform()

    #print("Number of Years: " + years_ )
    outElement = driver.find_element_by_name("finalvalue_with")
    tv = outElement.get_attribute('value')[1:]
    tv = tv.replace(',','')
    tv_num=float(tv)
    #print("Total Value: $" + str(tv_num) + " ($" + human_format(int(math.ceil(tv_num / 1000.0)) * 1000) + ")")
    num_shares = driver.find_element_by_name("numbershares_with")
    num_shares = num_shares.get_attribute('value').replace(',','')
    num_shares_num = int(float(num_shares))
    #print("New No of Shares: " + num_shares.get_attribute('value'))
    outElement = driver.find_element_by_name("sumdiv_with")
    ds = outElement.get_attribute('value')[1:]
    ds = ds.replace(',','')
    ds_num=float(ds)
    #print("Total Dividend Sum: $" + str(ds_num) + " ($" + human_format(int(math.ceil(ds_num / 1000.0)) * 1000) + ")")
    annualizedreturn_with = driver.find_element_by_name("annualizedreturn_with")
    #print("Annaulize Returns: " + annualizedreturn_with.get_attribute('value') +"%")

    result_table = [ years_,
                    "$" + human_format(int(math.ceil(tv_num / 1000.0)) * 1000),
                    str(num_shares_num),
                    "$" + human_format(int(math.ceil(ds_num / 1000.0)) * 1000),
                    annualizedreturn_with.get_attribute('value') + "%"]
    result_list.append(result_table)
  
  driver.quit()

  return result_list


def print_results(invest_amount, company_symbol, company_name, result_list, cur_price, avg_target_price, avg_stock_price_inc, new_sp_after_adj, avg_div, latest_dividend_amount):
  no_shares = int(invest_amount/cur_price)
  stock_info = [["Initial Investment:" , "$" + human_format(int(math.ceil(invest_amount / 1000.0)) * 1000) ],
        ["Company Symbol:" , company_symbol + " (" + company_name + ")" ],
        ["Initial Number of Shares:" , str(no_shares) ],
        ["Current Price:" , "$" + str(cur_price) ],
        ["Average Target Price:" , "$" + avg_target_price],
        ["Average Stock Price increase for this year:" , str(round(avg_stock_price_inc,2)) + "%"],
        ["Adjusted Stock Price increase for this year:" , str(round(new_sp_after_adj,2)) + "%"],
        ["Average Dividend Increase:" , str(round(avg_div,2)) + "%"],
        ["Latest Dividend Amount:" , "$"+ str(round(latest_dividend_amount,3))] ]
  print(tabulate(stock_info))
  print(tabulate(result_list))

def fetch_king_dividend_list():
  url_king_dividend_list = "https://dividendvaluebuilder.com/dividend-kings-list/"
  driver = getDriver(url_king_dividend_list, "Cannot Fetch Dividend Kings. Exiting...")
  html =driver.page_source
  driver.quit()
  soup = BeautifulSoup(html, 'html.parser')
  div_container = soup.find('div', class_="et_pb_section et_pb_section_2 et_section_regular")
  listofDK = [["No.", "Name of Company", "Years of Consec.\nDividend"]]
  for count, ptag in enumerate(div_container.find_all('p')):
    tmp = ptag.text.split('\n')
    if u'–' in tmp[0]:
      new_r = tmp[0].split(u'–')
      new_r.insert(0,count+1) 
      listofDK.append(new_r)
  print(tabulate(listofDK))

def add_option_parser():
  parser = OptionParser()
  parser.add_option("-s", "--symbol=", 
                    dest = "sym",
                    default="KO",
                    type="string",
                    help = "Name of the company to calulate dividend report (e.g. KO)")
  parser.add_option("-i", "--initial-investment=", 
                    dest = "ii",
                    default=16000,
                    type="int",
                    help = "Amount you are thinking to invest in (e.g. $16000)")
  parser.add_option("-a", "--adjusted-stock-percentage=", 
                    dest = "asp",
                    default=0,
                    type="int",
                    help = "Increase or decrease the \% for avg stocp rpice gain (e.g. 2,-2)")
  parser.add_option("--show", "--show-dividend-kings", 
                    dest = "sdk",
                    action="store_true",
                    default=False,
                    help = "Show Top 30 dividend king stocks")

  (options,args) = parser.parse_args()
  return options

def main():

  parser_options = add_option_parser()
  if(parser_options.sdk):
    fetch_king_dividend_list()
    exit(0)
  
  company_symbol =parser_options.sym
  invest_amount = parser_options.ii
  adjust_stock_price_increase = parser_options.asp
  
  DD = fetch_dividend_data(company_symbol)
  SP = fetch_stock_price_date(company_symbol, adjust_stock_price_increase)

  # DD[0] = latest_dividend_amount
  # DD[1] = avg_div
  # [cur_price, new_sp_after_adj, avg_target_price, avg_stock_price_inc, company_name]
  # SP[0] = cur_price
  # SP[1] = new_sp_after_adj
  # SP[2] = avg_target_price
  # SP[3] = avg_stock_price_inc
  # SP[4] = company_name
  result_list = calculate_compound_dividend(invest_amount, SP[0], DD[0], DD[1], SP[1])
  print_results(invest_amount, company_symbol, SP[4], result_list, SP[0], SP[2], SP[3], SP[1], DD[1], DD[0])

if __name__ == "__main__":
  main()
