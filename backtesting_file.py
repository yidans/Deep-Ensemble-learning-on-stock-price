from io import StringIO
import pandas as pd

class OptionsMLModel(QCAlgorithm):
    # Set up the strategy
    def Initialize(self):
        # Initialize date range and initial capital
        self.SetStartDate(2020, 2, 28)
        self.SetEndDate(2022, 2, 28)
        self.SetCash(100000)
        
        # Focus on Nvidia stock
        equity = self.AddEquity("NVDA", Resolution.Minute)
        equity.SetDataNormalizationMode(DataNormalizationMode.Raw)
        self.equity = equity.Symbol
        self.SetBenchmark(self.equity)
        
        # Focus on at-the-money options with TTE around one month
        option = self.AddOption("NVDA", Resolution.Minute)
        option.SetFilter(-3, 3, timedelta(20), timedelta(25))

        # Import price prediction data into dataframe
        qb = QuantBook()
        csv = qb.Download("https://www.dropbox.com/s/y9tlao1v4pyflzs/dnn_predicted_price.csv?dl=1")
        self.df = pd.read_csv(StringIO(csv))
    
    # Event handler for processing new data
    def OnData(self,data):
        # Retrieve current held options (if they exist)
        option_invested = [x.Key for x in self.Portfolio if x.Value.Invested and x.Value.Type==SecurityType.Option]
        
        # Already holding call options
        if option_invested:
            # Close call shortly before expiration
            if self.Time + timedelta(4) > option_invested[0].ID.Date:
                self.Liquidate(option_invested[0], "Too close to expiration")
            return
        
        # Format current date
        year = str(self.Time.year)
        month = str(self.Time.month)
        if self.Time.month < 10:
            month = "0" + month
        day = str(self.Time.day)
        if self.Time.day < 10:
            day = "0" + day
        cur_date = year + "-" + month + "-" + day
        
        # Initialize predicted price to -1
        # To cover case where future price cannot be retrieved
        predicted_price = -1
        
        # Search dataframe for price data at current date
        date_search = self.df.query("Date == @cur_date")
        
        # Current date entry found
        if len(date_search) > 0:
            cur_index = date_search.iloc[0]["Index"]
            
            # Calculate index of future entry
            # Note: 23 indices ahead corresponds to roughly one month
            future_index = cur_index + 20
            future_index_search = self.df.query("Index == @future_index")
            
            # Future date entry found, retrieve predicted price
            if len(future_index_search) > 0:
                predicted_price = self.df.iloc[future_index]["Predicted Price"]
        
        # Find currently trading price of stock
        adjusted_cur_price = float(self.Securities[self.equity].Price) / 4

        # Buy call options if price is predicted to rise
        if adjusted_cur_price < float(predicted_price):
            for i in data.OptionChains:
                chains = i.Value
                self.BuyCall(chains)
 
    # Logic for buying a call option contracts
    def BuyCall(self,chains):
        # Sort call contracts in decreasing order by TTE
        expiry = sorted(chains,key = lambda x: x.Expiry, reverse=True)[0].Expiry
        calls = [i for i in chains if i.Expiry == expiry and i.Right == OptionRight.Call]
        call_contracts = sorted(calls,key = lambda x: abs(x.Strike - x.UnderlyingLastPrice))
        
        # If no contracts are available, return
        if len(call_contracts) == 0: 
            return
        
        # The contract with the greatest TTE is selected
        self.call = call_contracts[0]
        
        # Determine quantity of call contracts to buy,
        # allocating 5% of the total capital each time
        quantity = self.Portfolio.TotalPortfolioValue / self.call.AskPrice
        quantity = int(0.05 * quantity / 100)
        self.Buy(self.call.Symbol, quantity)

    # Handle order events
    def OnOrderEvent(self, orderEvent):
        # Liquidate all held call options
        order = self.Transactions.GetOrderById(orderEvent.OrderId)
        if order.Type == OrderType.OptionExercise:
            self.Liquidate()
