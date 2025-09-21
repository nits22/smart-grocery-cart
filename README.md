# 🛒 Smart Grocery Cart - AI Agent

An intelligent grocery price comparison and cart optimization system powered by AI agents, web scraping, and LLM-driven insights.

## 🌟 Features

- **Real-time Price Scraping**: Automated price collection from major grocery delivery platforms (Blinkit, Swiggy Instamart, Zepto)
- **AI-Powered Optimization**: Intelligent cart optimization using LangChain agents with OpenAI/Gemini LLM integration
- **Multi-Store Comparison**: Compare prices across multiple stores (Blinkit, Swiggy Instamart, Zepto) and find the best prices
- **Smart Recommendations**: AI-generated shopping advice and money-saving tips
- **Interactive Web UI**: Clean Streamlit interface for easy shopping list management
- **Fallback System**: Robust fallback mechanisms with mock data when scraping fails
- **Cost Analysis**: Delivery fee calculations and total cost optimization

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Streamlit UI  │────│   AI Agent      │────│   Optimizers    │
│                 │    │   Orchestrator  │    │   (Greedy/ILP)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │              ┌─────────────────┐              │
         │              │  LangChain      │              │
         └──────────────│  Tools          │──────────────┘
                        │  - PriceChecker │
                        │  - Optimizer    │
                        └─────────────────┘
                                 │
                    ┌─────────────────────────────┐
                    │     Data Sources            │
                    │  ┌─────────┐ ┌─────────┐    │
                    │  │Blinkit  │ │Instamart│    │
                    │  │Scraper  │ │Scraper  │    │
                    │  └─────────┘ └─────────┘    │
                    │  ┌─────────┐ ┌─────────┐    │
                    │  │Supabase │ │Fallback │    │
                    │  │Cache    │ │Data     │    │
                    │  └─────────┘ └─────────┘    │
                    └─────────────────────────────┘
```

## 🚀 Quick Start

### 🎥 Demo Video

Watch the Smart Grocery Cart AI Agent in action:

![Smart Grocery Cart_AI_Agent](./assets/recording.gif)

### Prerequisites

- Python 3.9+
- API Keys for LLM services (OpenAI/Google Gemini)
- Supabase account (optional, for caching)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd smart-grocery-cart
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

4. **Run the application**
   ```bash
   streamlit run streamlit_real_app.py --server.port 8505
   ```

5. **Access the app**
   Open `http://localhost:8505` in your browser

## ⚙️ Configuration

### Environment Variables

Create a `.env` file with the following variables:

```env
# LLM API Keys (choose one or both for fallback)
OPENAI_API_KEY=your_openai_api_key_here
GOOGLE_API_KEY=your_google_api_key_here

# Supabase (optional - for price caching)
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_service_role_key

# Scraping Configuration
SCRAPING_TIMEOUT=90
MAX_PRODUCTS_PER_STORE=10
```

### LLM Priority Order

The system automatically handles LLM fallbacks in this order:
1. **Test LLM** (for development/demo - no API calls)
2. **OpenAI GPT-3.5-turbo** (primary choice)
3. **Google Gemini 1.5-flash** (fallback)

## 📱 Usage

### Web Interface

1. **Add Items**: Enter grocery items in the shopping list (one per line)
2. **Select Stores**: Choose which stores to compare (Blinkit, Instamart, etc.)
3. **Compare Prices**: Click "Compare Prices" to start AI analysis
4. **View Results**: See optimized cart with AI recommendations
5. **Optimize Further**: Use different optimization methods (Greedy/ILP)

### Example Shopping Lists

**Quick Test Items:**
```
milk
bread
eggs
```

**Weekly Groceries:**
```
Milk 1L
Bread
Eggs 12
Rice 5kg
Oil 1L
Curd 1L
```

### API Usage

You can also use the system programmatically:

```python
from ai_agent_with_llm_summary import GroceryCartAIAgent

# Initialize AI agent
agent = GroceryCartAIAgent()

# Find optimal cart
result = agent.find_optimal_cart(
    items=["milk", "bread", "eggs"],
    city="Mumbai",
    vendors=["Blinkit", "Swiggy Instamart"]
)

print(f"Total cost: ₹{result['total']}")
print(f"AI Summary: {result['ai_summary']}")
```

## 🧠 AI Agent Components

### Core Components

1. **GroceryCartAIAgent** (`ai_agent_with_llm_summary.py`)
   - Main AI orchestrator
   - LLM-powered summary generation
   - Lazy initialization for performance

2. **Agent Runner** (`agent_runner.py`)
   - LLM factory with multiple providers
   - Agent initialization and caching
   - Fallback mechanisms

3. **LangChain Tools** (`lc_tools.py`)
   - PriceCheckerTool: Web scraping interface
   - OptimizerTool: Cart optimization logic

4. **Orchestrators**
   - `agent_orchestrator.py`: LangChain-based orchestration
   - `working_orchestrator.py`: Fallback with mock data

### AI Features

- **Intelligent Summaries**: LLM analyzes optimization results and provides actionable advice
- **Cost Analysis**: Estimates savings compared to single-store shopping
- **Shopping Strategy**: Recommends which stores to visit first
- **Alternative Suggestions**: Suggests alternatives for unavailable items

## 🛠️ Technical Details

### Optimization Algorithms

1. **Greedy Algorithm** (Default)
   - Fast execution
   - Good results for most cases
   - O(n) time complexity

2. **Integer Linear Programming (ILP)**
   - Optimal solutions
   - Higher computational cost
   - Better for complex scenarios

### Data Flow

1. **Price Collection**: Scrape real-time prices from store APIs
2. **Caching**: Store results in Supabase for performance
3. **Fallback**: Use mock data if scraping fails
4. **Optimization**: Find best store combination
5. **AI Analysis**: Generate intelligent recommendations
6. **UI Display**: Present results with cost breakdowns

### Fallback System

The system includes multiple fallback layers:

- **Real Scraping** → **Cached Data** → **Mock Prices** → **Error Handling**
- **OpenAI LLM** → **Gemini LLM** → **Test LLM** → **Basic Summary**

## 🔧 Development

### Project Structure

```
smart-grocery-cart/
├── streamlit_real_app.py          # Main Streamlit UI
├── ai_agent_with_llm_summary.py   # AI Agent with LLM
├── agent_runner.py                # LLM factory and agent creation
├── agent_orchestrator.py          # LangChain orchestrator
├── working_orchestrator.py        # Fallback orchestrator
├── lc_tools.py                    # LangChain tools
├── optimizer.py                   # Optimization algorithms
├── blinkit_playwright_api.py      # Blinkit scraper
├── instamart_playwright_api.py    # Instamart scraper
├── cache_utils.py                 # Caching utilities
├── db_tools.py                    # Database operations
└── requirements.txt               # Dependencies
```

### Adding New Stores

1. Create scraper in `{store}_playwright_api.py`
2. Add store to `lc_tools.py` PriceCheckerTool
3. Add fallback prices in `working_orchestrator.py`
4. Update UI store selection in `streamlit_real_app.py`

### Adding New Items

Add fallback prices in `working_orchestrator.py`:

```python
FALLBACK_PRICES = {
    "new_item": {
        "Blinkit": {"price": 100.0, "available": True, "name": "Product Name"},
        "Swiggy Instamart": {"price": 105.0, "available": True, "name": "Product Name"}
    }
}
```

## 🐛 Troubleshooting

### Common Issues

1. **"AI agent not available"**
   - Check API keys in `.env` file
   - Verify OpenAI/Gemini quotas
   - System will fallback to working orchestrator

2. **"Items unavailable"**
   - Add items to `FALLBACK_PRICES` in `working_orchestrator.py`
   - Check store availability
   - Try simpler item names

3. **Scraping failures**
   - System automatically uses fallback data
   - Check internet connection
   - Verify store websites are accessible

4. **LLM quota exceeded**
   - System automatically switches to test LLM
   - Check API usage limits
   - Consider upgrading API plans

### Debug Mode

Enable debug mode in the UI to see:
- Raw orchestrator output
- API call details
- Error stack traces
- Performance metrics

## 📊 Performance

### Benchmarks

- **Price collection**: 2-5 seconds per store
- **Optimization**: <1 second for 10 items
- **AI summary**: 1-3 seconds (with API)
- **Total workflow**: 5-15 seconds

### Optimization

- Caching reduces repeated scraping
- Lazy initialization improves startup time
- Fallback systems ensure reliability
- Async operations where possible

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

### Development Setup

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
python -m pytest tests/

# Format code
black *.py

# Type checking
mypy *.py
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **LangChain**: For the agent framework
- **Streamlit**: For the web interface
- **Playwright**: For web scraping capabilities
- **OpenAI/Google**: For LLM services
- **Supabase**: For data storage and caching

## 📞 Support

For support, please:
1. Check the troubleshooting section
2. Search existing issues
3. Create a new issue with detailed description
4. Include debug logs and error messages

---

**Built with ❤️ for smarter grocery shopping**
