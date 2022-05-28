import numpy as np
import statistics as stat
import pandas

class NewsSectorRotation(QCAlgorithm):
    
    # PARAMETERS
    STOP_LOSS           = 0.15
    
    def Initialize(self):
        self.SetStartDate(2021, 2, 27)   # Set Start Date
        self.SetEndDate(2021, 9, 30)   # Set End Date
        self.SetCash(100000)  # Set Strategy Cash
        
        self.etfList = ["JETS", "XOP", "BDRY"] # airlines, oils/gas, and shipping ETFs
        for ticker in self.etfList:
            self.AddEquity(ticker, Resolution.Minute)
        self.AddEquity('SPY', Resolution.Minute)
        self.SetBenchmark('SPY')

        self.TrailData = [-1, -1, -1] # hold cur period's max price; used for stop lossing
        self.CurIndustryBenefits = [0,0,0] # populate at the end of each month with model outputs normalized by industry
        self.period = 0
        
        # self.benefits = [[-0.10216112, 0.03373282, -0.864106], [-0.22910343, 0.17941627, -0.5914803], 
        #                 [0.1885251, 0.06147055, 0.75000435], [-0.3137416, -0.53514135, 0.151117], 
        #                 [0.47459108, 0.39141858, 0.13399032], [0.06559482, -0.39495525, 0.53944993], 
        #                 [-0.14370073, -0.2124454, 0.6438539], [0.20762229, 0.24447055, -0.5479071], 
        #                 [0.43257174, -0.35560894, -0.21181929], [-0.043003738, -0.7836245, 0.17337184], 
        #                 [0.043780945, 0.4979885, -0.45823058], [-0.25218388, -0.687737, 0.060079128], 
        #                 [-0.28033766, -0.3551166, -0.3645457], [-0.2940743, -0.37920013, -0.32672554], 
        #                 [0.120712794, 0.6583781, -0.22090909], [-0.0752544, -0.30690813, -0.6178374], 
        #                 [0.11280515, -0.07110819, 0.81608665], [-0.34482485, -0.30600023, 0.3491749], 
        #                 [0.50233287, 0.23761241, 0.26005468], [0.09778221, -0.079956494, -0.8222613], 
        #                 [0.036488887, -0.25465578, -0.70885533], [0.42780337, 0.5440793, 0.02811735], 
        #                 [0.16731668, 0.31934142, 0.5133419], [-0.114730634, 0.24385075, 0.64141864], 
        #                 [0.261057, 0.33647937, 0.40246364], [0.047175642, -0.10399269, 0.84883165], 
        #                 [-0.10166555, 0.028542416, 0.86979204], [0.16440171, 0.39367843, -0.4419198], 
        #                 [-0.23345852, 0.011007223, 0.75553435], [-0.26527596, 0.058601767, 0.67612225], 
        #                 [0.12141009, -0.3759418, 0.50264806], [0.28355277, 0.3914483, 0.32499897], 
        #                 [0.13894679, 0.50196666, 0.3590866]]

        # self.benefits = [[0.14301048, 0.33546808, -0.52152145], [0.20313305, -0.3211921, -0.4756748], 
        #                 [-0.055825587, -0.49146628, 0.45270813], [-0.015129141, -0.9586664, 0.026204465], 
        #                 [-0.002849246, -0.62397295, 0.37317774], [0.04153592, -0.47064197, -0.48782215], 
        #                 [0.19427727, -0.7300464, 0.07567639], [-0.21685933, -0.68378776, 0.09935288], 
        #                 [0.23621808, -0.5917347, 0.17204726], [-0.07836599, -0.5471862, -0.3744478], 
        #                 [-0.11500821, -0.8662294, -0.018762419]]
                        
        # self.benefits = [[-0.008638579, -0.545828, -0.4455335], [-0.031846713, -0.46543312, 0.5027202], 
        #                 [0.19717455, -0.32541195, -0.47741354], [0.27291736, -0.66481197, 0.06227071], 
        #                 [-0.07016502, -0.542956, 0.38687903], [0.18620506, -0.5573772, 0.2564177], 
        #                 [0.11434493, -0.4105169, -0.47513816], [0.1295173, -0.8307885, 0.039694205]]
        
        self.benefits = [[0.17164788, -0.64025986, -0.18809232], [0.11272468, -0.8159314, 0.07134394], 
                        [-0.22690034, -0.5014006, 0.2716991], [0.21800405, -0.46319234, 0.31880355], 
                        [0.10157594, -0.6229355, -0.27548853], [0.13315336, -0.82694036, 0.03990628]]

        # will want a scheduling function to go through constructing TrailData, NewsProportions, and maxBenefit each month
        self.Schedule.On(self.DateRules.MonthStart("SPY"), self.TimeRules.AfterMarketOpen('SPY'), self.Rebalance)


    # should check to see if we hit a trailing stop loss & if so, liquidate and call rebalance to place investment in the sector with the next-best projected earnings
    def OnData(self, data):
        '''OnData event is the primary entry point for your algorithm. Each new data point will be pumped in here.
            Arguments:
                data: Slice object keyed by symbol containing the stock data
        '''

        # setting / updating TrailData with (starting price, max, dummy) & drawdown
        for idx in range(len(self.etfList)):
            curPrice = self.Securities[self.etfList[idx]].Price
            if self.TrailData[idx] == -1:
                self.TrailData[idx] = curPrice
            else:
                self.TrailData[idx] = max(self.TrailData[idx], curPrice)
                if curPrice < self.TrailData[idx] * (1 - self.STOP_LOSS):
                    self.CurIndustryBenefits[idx] = 0
                    self.NormalizeBenefits()
                    self.TakePositions()
                
    def NormalizeBenefits(self):
        absBen = [abs(ben) for ben in self.CurIndustryBenefits]
        absBen = sum(absBen)
        if absBen == 0: absBen = 1
        self.CurIndustryBenefits = [ben/absBen for ben in self.CurIndustryBenefits]

    def GetBenefits(self):
        self.CurIndustryBenefits = self.benefits[self.period]

    # should use "maxBenefit" array, find the actual max + associated stock
    # Either... (1) place that in a object called "chosenPosition" & then in Rebalance, you always want to be investing in "chosenPosition"
    # Or... (2) you can take the position here... and in Rebalance... you would want to monitor for stop lossing
    def TakePositions(self):
        for i in range(len(self.CurIndustryBenefits)):
            self.SetHoldings(self.etfList[i], self.CurIndustryBenefits[i])

    def Rebalance(self):
        self.ResetHoldingsAndData()
        self.GetBenefits()
        self.TakePositions()
        self.period += 1

    def ResetHoldingsAndData(self):
        self.Debug('resetting holdings')
        self.Liquidate()
        self.CurIndustryBenefits = [0,0,0]
        self.TrailData = [-1, -1, -1]
