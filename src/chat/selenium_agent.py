# selenium_agent.py

from typing import Optional
import random

from phi.agent import Agent
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.keys import Keys

class SeleniumAgent(Agent):
    def __init__(
        self,
        browser: str = "chrome",
        headless: bool = False,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.browser = browser
        self.headless = headless
        self.driver = None
        
        # List of random search queries
        self.random_queries = [
            "fascinating facts about space",
            "cute puppies playing",
            "best recipes for beginners",
            "amazing natural phenomena",
            "funny cat videos",
            "interesting historical events",
            "beautiful travel destinations",
            "latest technology news",
            "mind-bending optical illusions",
            "easy DIY projects"
        ]

    def startup(self) -> None:
        """Initialize the Selenium WebDriver"""
        if self.browser.lower() == "chrome":
            options = webdriver.ChromeOptions()
            if self.headless:
                options.add_argument("--headless")
            self.driver = webdriver.Chrome(options=options)
        else:
            raise ValueError(f"Unsupported browser: {self.browser}")

    def shutdown(self) -> None:
        """Clean up the WebDriver"""
        if self.driver:
            self.driver.quit()

    def google_search(self) -> str:
        """Perform a random Google search"""
        try:
            # Navigate to Google
            self.driver.get("https://www.google.com")
            
            # Wait for and accept any cookie consent if present (common in some regions)
            try:
                consent_button = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button[id='L2AGLb']"))
                )
                consent_button.click()
            except TimeoutException:
                pass  # No consent button found, continue
            
            # Get search box and enter query
            search_query = random.choice(self.random_queries)
            search_box = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.NAME, "q"))
            )
            search_box.send_keys(search_query)
            search_box.send_keys(Keys.RETURN)
            
            return f"Successfully searched for: {search_query}"
            
        except Exception as e:
            return f"Error performing Google search: {str(e)}"

    def run(self, task: str) -> str:
        """Execute a task"""
        if not self.driver:
            return "Error: WebDriver not initialized"
            
        if task == "random_google_search":
            return self.google_search()
        else:
            return f"Unknown task: {task}"

# Example usage
if __name__ == "__main__":    
    agent = SeleniumAgent(
        name="selenium_agent",
        browser="chrome",
        headless=False  # Set to False to see the browser in action
    )
    
    # Start the agent
    agent.startup()
    
    # Perform random Google search
    result = agent.run("random_google_search")
    print(result)
    
    # Wait a few seconds to see the results
    import time
    time.sleep(5)
        
    # Cleanup
    agent.shutdown()