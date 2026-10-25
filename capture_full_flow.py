import os
import time
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

CAPTURES_DIR = r"c:\Users\ganes\OneDrive\QORE\website_captures"
os.makedirs(CAPTURES_DIR, exist_ok=True)

options = Options()
options.add_argument("--headless=new")
options.add_argument("--window-size=1920,1080")
options.add_argument("--disable-gpu")
options.add_argument("--force-device-scale-factor=1")

driver = webdriver.Edge(options=options)
driver.set_window_size(1920, 1080)

try:
    print("Opening QORE...")
    driver.get("http://127.0.0.1:8000/")
    time.sleep(2)

    # 1. Dismiss WelcomeModal
    try:
        enter_btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CLASS_NAME, "qore-enter-studio-btn"))
        )
        enter_btn.click()
        print("Clicked WelcomeModal enter button")
        time.sleep(1)
    except Exception as e:
        print("Welcome button error:", e)

    # 2. Open Explorer file openqasm/qaoa_cut.qasm
    try:
        # First ensure 'openqasm' folder is expanded if needed or click directly on qaoa_cut.qasm
        qaoa_file = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//*[contains(@title, 'qaoa_cut.qasm') or contains(text(), 'qaoa_cut.qasm')]"))
        )
        qaoa_file.click()
        print("Clicked qaoa_cut.qasm in Explorer")
        time.sleep(2)
    except Exception as e:
        print("qaoa_cut.qasm click error:", e)

    # Capture 1: Studio with openqasm/qaoa_cut.qasm
    p1 = os.path.join(CAPTURES_DIR, "01_studio_qaoa_cut_code.png")
    driver.save_screenshot(p1)
    print("Saved:", p1)

    # 3. Click Unitary Matrix tab in Studio Inspector
    try:
        unitary_tab = driver.find_element(By.XPATH, "//button[contains(text(), 'Unitary') or contains(@class, 'inspector-tab-btn') and contains(text(), 'Matrix')]")
        unitary_tab.click()
        time.sleep(1)
        print("Switched to Unitary inspector")
    except Exception as e:
        print("Unitary tab click error:", e)

    p2 = os.path.join(CAPTURES_DIR, "02_studio_unitary_matrix.png")
    driver.save_screenshot(p2)
    print("Saved:", p2)

    # 4. Click Bloch tab in Studio Inspector
    try:
        bloch_tab = driver.find_element(By.XPATH, "//button[contains(text(), 'Bloch')]")
        bloch_tab.click()
        time.sleep(1)
        print("Switched to Bloch inspector")
    except Exception as e:
        print("Bloch tab click error:", e)

    p3 = os.path.join(CAPTURES_DIR, "03_studio_bloch_view.png")
    driver.save_screenshot(p3)
    print("Saved:", p3)

    # 5. Click Run / Simulate button
    try:
        run_btn = driver.find_element(By.XPATH, "//button[contains(., 'Run') or contains(., 'Simulate')]")
        run_btn.click()
        print("Clicked Run/Simulate button")
        time.sleep(3)
    except Exception as e:
        print("Run button error:", e)

    # 6. Switch to Lab Tab
    try:
        lab_nav = driver.find_element(By.XPATH, "//*[@title='Simulation' or contains(@class, 'activity-item') and contains(., 'Lab')]")
        lab_nav.click()
        print("Switched to Lab Tab")
        time.sleep(2)
    except Exception as e:
        print("Lab nav error:", e)

    p4 = os.path.join(CAPTURES_DIR, "04_lab_aer_simulation.png")
    driver.save_screenshot(p4)
    print("Saved:", p4)

    # 7. Switch to Forge Tab
    try:
        forge_nav = driver.find_element(By.XPATH, "//*[@title='Optimization' or contains(@class, 'activity-item') and contains(., 'Forge')]")
        forge_nav.click()
        print("Switched to Forge Tab")
        time.sleep(2)
    except Exception as e:
        print("Forge nav error:", e)

    p5 = os.path.join(CAPTURES_DIR, "05_forge_optimization.png")
    driver.save_screenshot(p5)
    print("Saved:", p5)

finally:
    driver.quit()
    print("Selenium finished.")
