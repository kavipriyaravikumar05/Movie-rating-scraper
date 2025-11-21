import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
import re

class IMDbScraper:
    def __init__(self, headless=True):  # Fixed: double underscores
        self.headless = headless
        self.driver = None
        self.movie_data = []        
    
    def setup_driver(self):
        chrome_options = Options()
        if self.headless: 
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)    
    
    def scrape_top_movies(self):
        try:
            print("🚀 Setting up Chrome Driver in headless mode...")
            self.setup_driver()
            print("📡 Loading IMDb Top 250 page...")
            self.driver.get("https://www.imdb.com/chart/top/")
            
            # Wait for the page to load completely
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "li.ipc-metadata-list-summary-item"))
            )
            print("✅ Page loaded. Starting data extraction...")
            time.sleep(2)
           
            # Extract all movie data using JavaScript execution
            movies_data = self.driver.execute_script("""
                var movies = [];
                var movieElements = document.querySelectorAll('li.ipc-metadata-list-summary-item');
                
                for (var i = 0; i < Math.min(250, movieElements.length); i++) {
                    var element = movieElements[i];
                    var titleElement = element.querySelector('h3.ipc-title__text');
                    var metadataElement = element.querySelector('.cli-title-metadata');
                    var ratingElement = element.querySelector('span.ipc-rating-star--rating');
                    
                    var title = 'Unknown';
                    var year = 'Unknown';
                    var rating = 'N/A';
                    var duration = 'Unknown';
                    
                    // Extract title
                    if (titleElement) {
                        title = titleElement.textContent.trim();
                        // Remove rank number (e.g., "1. The Shawshank Redemption")
                        if (title.includes('. ')) {
                            title = title.split('. ').slice(1).join('. ');
                        }
                    }
                    
                    // Extract year and duration from metadata
                    if (metadataElement) {
                        var spans = metadataElement.querySelectorAll('span');
                        if (spans.length > 0) {
                            year = spans[0].textContent.trim();
                        }
                        if (spans.length > 1) {
                            duration = spans[1].textContent.trim();
                        }
                    }
                    
                    // Extract rating
                    if (ratingElement) {
                        rating = ratingElement.textContent.trim();
                    }
                    
                    movies.push({
                        rank: i + 1,
                        title: title,
                        year: year,
                        duration: duration,
                        rating: rating
                    });
                }
                return movies;
            """)
            
            for movie in movies_data:
                self.movie_data.append({
                    'rank': movie['rank'], 
                    'title': movie['title'], 
                    'year': movie['year'],
                    'duration': movie['duration'],
                    'imdb_rating': movie['rating'], 
                    'scraped_at': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
                })
                print(f"🎬 {movie['rank']:3d}. {movie['title']} ({movie['year']}) - {movie['rating']}")
            
            print(f"✅ Primary method extracted {len(self.movie_data)} movies")
            
            # Check if we have missing titles and use backup method
            missing_titles = sum(1 for movie in self.movie_data if movie['title'] == 'Unknown' or movie['title'].startswith('#'))
            if missing_titles > 0:
                print(f"🔄 {missing_titles} movies have missing titles. Using backup extraction...")
                self.backup_title_extraction()
                
        except Exception as e:
            print(f"❌ Error during scraping: {e}")
        finally:
            if self.driver: 
                self.driver.quit()
    
    def backup_title_extraction(self):
        """Backup method that works reliably for all titles"""
        try:
            print("🔄 Using reliable backup title extraction...")
            
            # Get all movie containers
            movie_elements = self.driver.find_elements(By.CSS_SELECTOR, "li.ipc-metadata-list-summary-item")
            
            for i, element in enumerate(movie_elements[:250]):
                try:
                    # METHOD 1: Try to find title using the h3 element
                    try:
                        title_element = element.find_element(By.CSS_SELECTOR, "h3.ipc-title__text")
                        title_text = title_element.text.strip()
                        if '. ' in title_text:
                            title = title_text.split('. ', 1)[1]
                        else:
                            title = title_text
                    except:
                        # METHOD 2: Use data-testid attribute for reliable extraction
                        try:
                            title_link = element.find_element(By.CSS_SELECTOR, "a[data-testid]")
                            title = title_link.get_attribute('textContent').strip()
                            if '. ' in title:
                                title = title.split('. ', 1)[1]
                        except:
                            # METHOD 3: Fallback to text analysis
                            full_text = element.text
                            lines = [line.strip() for line in full_text.split('\n') if line.strip()]
                            title = f"#{(i+1)}"
                            for line in lines:
                                if (len(line) > 10 and 
                                    not line.replace('.', '').isdigit() and 
                                    not line.startswith('Rate') and
                                    not line.endswith('m') and
                                    any(keyword in line.lower() for keyword in ['the', 'and', 'of', 'a', 'in', 'to'])):
                                    if '. ' in line:
                                        potential_title = line.split('. ', 1)[1]
                                        if len(potential_title) > 3:
                                            title = potential_title
                                            break
                                    else:
                                        if len(line) > 3:
                                            title = line
                                            break
                    
                    # Extract year if still unknown
                    year = 'Unknown'
                    try:
                        metadata = element.find_element(By.CSS_SELECTOR, ".cli-title-metadata")
                        year_spans = metadata.find_elements(By.TAG_NAME, "span")
                        if year_spans:
                            year = year_spans[0].text.strip()
                    except:
                        pass
                    
                    # Extract rating
                    rating = 'N/A'
                    try:
                        rating_element = element.find_element(By.CSS_SELECTOR, "span.ipc-rating-star--rating")
                        rating = rating_element.text.strip()
                    except:
                        pass
                    
                    # Update movie data
                    if i < len(self.movie_data):
                        self.movie_data[i]['title'] = title
                        self.movie_data[i]['year'] = year
                        self.movie_data[i]['imdb_rating'] = rating
                    else:
                        self.movie_data.append({
                            'rank': i + 1,
                            'title': title,
                            'year': year,
                            'imdb_rating': rating,
                            'scraped_at': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
                        })
                    
                    print(f"🔄 Fixed: {i+1:3d}. {title} ({year}) - {rating}")
                    
                except Exception as e:
                    print(f"⚠  Error processing movie {i+1}: {e}")
                    continue
                    
            print("✅ Backup title extraction completed")
            
        except Exception as e:
            print(f"❌ Backup title extraction failed: {e}")
    
    def save_to_csv(self, filename="imdb_top_movies.csv"):
        if not self.movie_data: 
            print("❌ No data to save!")
            return False
        
        df = pd.DataFrame(self.movie_data)
        # Ensure we have all expected columns
        if 'duration' not in df.columns:
            df['duration'] = 'Unknown'
        
        df = df[['rank', 'title', 'year', 'duration', 'imdb_rating', 'scraped_at']]
        df.to_csv(filename, index=False, encoding='utf-8')
        
        print(f"💾 Data saved to {filename}")
        print(f"📊 Total movies: {len(self.movie_data)}")
        
        # Count proper titles
        proper_titles = len([movie for movie in self.movie_data if not movie['title'].startswith('#') and movie['title'] != 'Unknown'])
        
        print(f"🎬 Movies with proper titles: {proper_titles}/250")
        print(f"📅 Movies with proper years: {len([movie for movie in self.movie_data if movie['year'] != 'Unknown'])}/250")
        
        print("\n" + "="*80)
        print("FIRST 10 MOVIES:")
        print("="*80)
        print(df.head(10).to_string(index=False))
        
        # Show sample from middle to verify data quality
        if len(df) >= 20:
            print("\n" + "="*80)
            print("SAMPLE MOVIES 100-110:")
            print("="*80)
            print(df.iloc[99:109].to_string(index=False))
            
        return True

def main():
    print("🎬 IMDb TOP 250 SCRAPER - HEADLESS MODE 🎬")
    print("="*50)
    print("🌐 Chrome will run in invisible mode")
    print("⏳ This may take 20-30 seconds...")
    print("="*50)
    
    # Set headless=True for invisible browser
    scraper = IMDbScraper(headless=True)
    start_time = time.time()
    scraper.scrape_top_movies()
    end_time = time.time()
    
    if scraper.movie_data:
        filename = "imdb_top_movies.csv"
        if scraper.save_to_csv(filename):
            print(f"\n✅ SUCCESS! Scraping completed in {end_time - start_time:.2f} seconds")
            print(f"📁 Output file: {filename}")
            
            # Final statistics
            proper_titles = len([movie for movie in scraper.movie_data if not movie['title'].startswith('#') and movie['title'] != 'Unknown'])
            
            print(f"\n📊 FINAL STATISTICS:")
            print(f"   • Total movies extracted: {len(scraper.movie_data)}/250")
            print(f"   • Movies with proper titles: {proper_titles}/250")
            print(f"   • Movies with proper years: {len([movie for movie in scraper.movie_data if movie['year'] != 'Unknown'])}/250")
            print(f"   • Execution time: {end_time - start_time:.2f} seconds")
            
            if proper_titles == 250:
                print("   🎉 ALL 250 movie titles extracted successfully!")
            else:
                print(f"   ⚠  {250 - proper_titles} movie titles may be missing")
    else:
        print("❌ No data was scraped!")

if __name__ == "__main__":  # Fixed: double underscores
    main()