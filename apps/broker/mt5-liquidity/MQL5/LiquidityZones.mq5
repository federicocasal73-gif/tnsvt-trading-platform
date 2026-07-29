//+------------------------------------------------------------------+
//|                                              LiquidityZones.mq5   |
//|                       TNSVT - Terminal Financiera Pro             |
//|                                                                   |
//|  LiquidityZones Expert Advisor                                    |
//|                                                                   |
//|  Detects liquidity structures on MT5 charts:                       |
//|    - Swing Highs/Lows (over N bars)                               |
//|    - Equal Highs/Lows (liquidity pools, double tops/bottoms)      |
//|    - Fair Value Gaps (3-candle imbalance)                         |
//|    - Break of Structure (BOS)                                     |
//|                                                                   |
//|  Publishes detected zones to liquidity-engine Python service       |
//|  via WebRequest on every new bar (configurable interval).         |
//|                                                                   |
//|  Author: TNSVT  Version: 1.0                                      |
//+------------------------------------------------------------------+
#property copyright "TNSVT - Terminal Financiera Pro"
#property version   "1.00"
#property description "Liquidity Zones detector + publisher to TNSVT liquidity-engine"
#property strict

#include <LiquidityStructures.mqh>

//--- Input parameters
input string  InpWebhookURL       = "http://localhost:8047";   // Webhook URL (liquidity-engine)
input int     InpWebhookPort      = 8047;                       // Webhook port
input string  InpWebhookPath      = "/zones";                   // Webhook path
input int     InpPublishSeconds   = 60;                         // Publish interval (seconds)
input int     InpSwingLookback    = 5;                          // Swing lookback (bars each side)
input double  InpEqualTolerancePts= 5.0;                        // Equal level tolerance (points)
input double  InpMinFVGSizePts    = 10.0;                       // Min FVG size (points)
input int     InpMaxZonesPerCycle = 30;                         // Max zones sent per cycle
input bool    InpDrawOnChart      = true;                       // Draw zones on chart
input color   InpColorSwingHigh   = clrCrimson;                 // Color: swing high
input color   InpColorSwingLow    = clrDodgerBlue;              // Color: swing low
input color   InpColorEqualHigh   = clrMagenta;                 // Color: equal high
input color   InpColorEqualLow    = clrAqua;                    // Color: equal low
input color   InpColorFVGBull     = clrLime;                    // Color: FVG bull
input color   InpColorFVGBear     = clrOrangeRed;               // Color: FVG bear
input string  InpAccountID        = "";                         // Account identifier (auto if empty)

//--- Globals
datetime g_lastBarTime    = 0;
datetime g_lastPublish    = 0;
int      g_swingLookback   = 5;
double   g_equalTolerance = 5.0;
double   g_minFVGSize     = 10.0;
string   g_accountID      = "";
string   g_webhookURL     = "";
int      g_webhookPort    = 0;
string   g_webhookPath    = "";

//--- Storage
SLiquidityZone g_zones[];

//+------------------------------------------------------------------+
//| Expert initialization function                                    |
//+------------------------------------------------------------------+
int OnInit()
{
   PrintFormat("[LiquidityZones] EA init on %s %s | Account: %lld",
               _Symbol, EnumToString(Period()), (long)AccountInfoInteger(ACCOUNT_LOGIN));

   // Apply inputs to globals
   g_swingLookback   = MathMax(2, InpSwingLookback);
   g_equalTolerance  = InpEqualTolerancePts;
   g_minFVGSize     = InpMinFVGSizePts;
   g_webhookURL     = InpWebhookURL;
   g_webhookPort    = InpWebhookPort;
   g_webhookPath    = InpWebhookPath;

   if(StringLen(InpAccountID) > 0)
      g_accountID = InpAccountID;
   else
      g_accountID = StringFormat("%lld", (long)AccountInfoInteger(ACCOUNT_LOGIN));

   // Strip protocol prefix from URL for WebRequest
   if(StringFind(g_webhookURL, "http://") == 0)
      g_webhookURL = StringSubstr(g_webhookURL, 7);

   // Validate bar history available
   int minBars = g_swingLookback * 2 + 50;
   if(Bars(_Symbol, Period()) < minBars)
   {
      PrintFormat("[LiquidityZones] Not enough bars (have %d, need %d). EA disabled.",
                  Bars(_Symbol, Period()), minBars);
      return INIT_FAILED;
   }

   // Initial detection so zones are visible immediately
   DetectAllZones();

   PrintFormat("[LiquidityZones] Initialized: webhook=%s:%d%s, swing_lookback=%d, "
               "equal_tol=%.1f pts, min_fvg=%.1f pts",
               g_webhookURL, g_webhookPort, g_webhookPath, g_swingLookback,
               g_equalTolerance, g_minFVGSize);
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization                                            |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   ObjectsDeleteAll(0, "LZ_");
   PrintFormat("[LiquidityZones] EA removed (reason=%d)", reason);
}

//+------------------------------------------------------------------+
//| Expert tick function (avoid heavy work, gate by bar time)        |
//+------------------------------------------------------------------+
void OnTick()
{
   datetime barTime = iTime(_Symbol, Period(), 0);

   // Only process on new bar (avoid recompute every tick)
   if(barTime == g_lastBarTime)
      return;
   g_lastBarTime = barTime;

   // Detect all zones on bar close
   DetectAllZones();

   // Publish at configured interval
   int now = (int)TimeCurrent();
   if(now - (int)g_lastPublish >= InpPublishSeconds)
   {
      PublishZones();
      g_lastPublish = now;
   }
}

//+------------------------------------------------------------------+
//| Detect all liquidity structures                                   |
//+------------------------------------------------------------------+
void DetectAllZones()
{
   ArrayResize(g_zones, 0);

   int totalBars = Bars(_Symbol, Period());
   if(totalBars < g_swingLookback * 2 + 3) return;

   int lookback = MathMin(totalBars - g_swingLookback - 1, 500);

   //--- 1. Swing highs/lows
   DetectSwingHighs(lookback);
   DetectSwingLows(lookback);

   //--- 2. Equal highs/lows (within tolerance, separated by <= 30 bars)
   DetectEqualLevels(lookback);

   //--- 3. Fair Value Gaps (3-candle imbalance)
   DetectFVGs(lookback);

   //--- 4. Break of Structure (close beyond swing high/low)
   DetectBOS(lookback);

   //--- Trim to max zones (keep most recent)
   if(ArraySize(g_zones) > InpMaxZonesPerCycle)
      TrimZones(InpMaxZonesPerCycle);

   //--- Draw on chart
   if(InpDrawOnChart)
      DrawZones();
}

//+------------------------------------------------------------------+
//| Swing highs: bar i is highest among [i-N..i+N]                    |
//+------------------------------------------------------------------+
void DetectSwingHighs(int lookback)
{
   int count = 0;
   for(int i = g_swingLookback; i < lookback; i++)
   {
      double hi = iHigh(_Symbol, Period(), i);
      if(hi <= 0) continue;

      bool isSwing = true;
      for(int j = 1; j <= g_swingLookback; j++)
      {
         double otherHi = iHigh(_Symbol, Period(), i + j);
         double otherLo = iLow(_Symbol, Period(), i + j);
         if(otherHi >= hi || otherLo >= hi)
         {
            isSwing = false;
            break;
         }
      }
      if(!isSwing) continue;

      SLiquidityZone z;
      ZeroMemory(z);
      z.type       = ZONE_SWING_HIGH;
      z.price_high = hi;
      z.price_low  = iLow(_Symbol, Period(), i);
      z.time_start = iTime(_Symbol, Period(), i);
      z.time_end   = iTime(_Symbol, Period(), 0);
      z.strength   = 1;
      z.swept      = false;
      InitZone(z);

      AddZone(z);
      count++;
      if(count > 50) break;  // safety
   }
}

//+------------------------------------------------------------------+
//| Swing lows: bar i is lowest among [i-N..i+N]                     |
//+------------------------------------------------------------------+
void DetectSwingLows(int lookback)
{
   int count = 0;
   for(int i = g_swingLookback; i < lookback; i++)
   {
      double lo = iLow(_Symbol, Period(), i);
      if(lo <= 0) continue;

      bool isSwing = true;
      for(int j = 1; j <= g_swingLookback; j++)
      {
         double otherHi = iHigh(_Symbol, Period(), i + j);
         double otherLo = iLow(_Symbol, Period(), i + j);
         if(otherLo <= lo || otherHi <= lo)
         {
            isSwing = false;
            break;
         }
      }
      if(!isSwing) continue;

      SLiquidityZone z;
      ZeroMemory(z);
      z.type       = ZONE_SWING_LOW;
      z.price_high = iHigh(_Symbol, Period(), i);
      z.price_low  = lo;
      z.time_start = iTime(_Symbol, Period(), i);
      z.time_end   = iTime(_Symbol, Period(), 0);
      z.strength   = 1;
      z.swept      = false;
      InitZone(z);

      AddZone(z);
      count++;
      if(count > 50) break;
   }
}

//+------------------------------------------------------------------+
//| Equal highs/lows (liquidity pools): two swing highs/lows         |
//| within tolerance, separated by 5..100 bars                         |
//+------------------------------------------------------------------+
void DetectEqualLevels(int lookback)
{
   int max = ArraySize(g_zones);
   for(int i = 0; i < max; i++)
   {
      if(g_zones[i].type != ZONE_SWING_HIGH && g_zones[i].type != ZONE_SWING_LOW)
         continue;

      for(int j = i + 1; j < max; j++)
      {
         if(g_zones[i].type != g_zones[j].type) continue;

         datetime tDiff = g_zones[i].time_start - g_zones[j].time_start;
         if(tDiff < 5 * PeriodSeconds() || tDiff > 100 * PeriodSeconds()) continue;

         double refPrice = g_zones[i].type == ZONE_SWING_HIGH
                         ? g_zones[i].price_high
                         : g_zones[i].price_low;
         double otherPrice = g_zones[i].type == ZONE_SWING_HIGH
                           ? g_zones[j].price_high
                           : g_zones[j].price_low;

         if(!AreEqualLevels(refPrice, otherPrice, g_equalTolerance)) continue;

         // Mark the original as an equal-level zone (preserve original swing)
         SLiquidityZone z;
         ZeroMemory(z);
         z.type = (g_zones[i].type == ZONE_SWING_HIGH) ? ZONE_EQUAL_HIGH : ZONE_EQUAL_LOW;
         z.price_high = MathMax(refPrice, otherPrice);
         z.price_low  = MathMin(refPrice, otherPrice);
         z.time_start = MathMin(g_zones[i].time_start, g_zones[j].time_start);
         z.time_end   = iTime(_Symbol, Period(), 0);
         z.strength   = 2;
         z.swept      = false;
         InitZone(z);
         AddZone(z);

         break;  // only mark one equal pair per swing
      }
   }
}

//+------------------------------------------------------------------+
//| Fair Value Gaps: 3 consecutive candles where candle[2].low >     |
// candle[0].high (bull) or candle[2].high < candle[0].low (bear)    |
//+------------------------------------------------------------------+
void DetectFVGs(int lookback)
{
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if(point <= 0) point = 0.00001;
   double minSize = g_minFVGSize * point;

   for(int i = g_swingLookback; i < lookback - 2; i++)
   {
      double hi_0 = iHigh(_Symbol, Period(), i + 2);
      double lo_0 = iLow(_Symbol, Period(), i + 2);
      double hi_2 = iHigh(_Symbol, Period(), i);
      double lo_2 = iLow(_Symbol, Period(), i);

      // Bullish FVG: candle[i+2] is below, candle[i] is above (gap up)
      if(lo_0 > hi_2)
      {
         double gapSize = lo_0 - hi_2;
         if(gapSize >= minSize)
         {
            SLiquidityZone z;
            ZeroMemory(z);
            z.type       = ZONE_FVG_BULL;
            z.price_high = lo_0;
            z.price_low  = hi_2;
            z.time_start = iTime(_Symbol, Period(), i);
            z.time_end   = iTime(_Symbol, Period(), 0);
            z.strength   = 1;
            z.swept      = false;
            InitZone(z);
            AddZone(z);
         }
      }

      // Bearish FVG: candle[i+2] is above, candle[i] is below (gap down)
      if(hi_0 < lo_2)
      {
         double gapSize = lo_2 - hi_0;
         if(gapSize >= minSize)
         {
            SLiquidityZone z;
            ZeroMemory(z);
            z.type       = ZONE_FVG_BEAR;
            z.price_high = lo_2;
            z.price_low  = hi_0;
            z.time_start = iTime(_Symbol, Period(), i);
            z.time_end   = iTime(_Symbol, Period(), 0);
            z.strength   = 1;
            z.swept      = false;
            InitZone(z);
            AddZone(z);
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Break of Structure: candle closes beyond a swing high/low         |
//+------------------------------------------------------------------+
void DetectBOS(int lookback)
{
   for(int i = 0; i < ArraySize(g_zones); i++)
   {
      if(g_zones[i].type != ZONE_SWING_HIGH && g_zones[i].type != ZONE_SWING_LOW)
         continue;

      // Look at subsequent candles
      for(int j = (int)(g_zones[i].time_start - iTime(_Symbol, Period(), lookback - 1)) / PeriodSeconds();
          j > 0 && j < lookback - 1; j--)
      {
         double close = iClose(_Symbol, Period(), j);
         if(close <= 0) continue;

         bool isBullBOS = (g_zones[i].type == ZONE_SWING_HIGH) && (close > g_zones[i].price_high);
         bool isBearBOS = (g_zones[i].type == ZONE_SWING_LOW)  && (close < g_zones[i].price_low);

         if(isBullBOS || isBearBOS)
         {
            SLiquidityZone z;
            ZeroMemory(z);
            z.type       = isBullBOS ? ZONE_BOS_BULL : ZONE_BOS_BEAR;
            z.price_high = isBullBOS ? close : g_zones[i].price_high;
            z.price_low  = isBullBOS ? g_zones[i].price_high : close;
            z.time_start = iTime(_Symbol, Period(), j);
            z.time_end   = iTime(_Symbol, Period(), 0);
            z.strength   = 1;
            z.swept      = false;
            InitZone(z);
            AddZone(z);
            break;
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Append zone to g_zones (skip if too close to last added)         |
//+------------------------------------------------------------------+
void AddZone(const SLiquidityZone &z)
{
   if(ArraySize(g_zones) >= 100) return;  // hard cap

   // Deduplicate: skip if same type and very close midpoint to recent
   for(int i = ArraySize(g_zones) - 1; i >= 0 && i >= ArraySize(g_zones) - 5; i--)
   {
      if(g_zones[i].type == z.type &&
         MathAbs(g_zones[i].midpoint - z.midpoint) < MathMax(g_minFVGSize, 1) * SymbolInfoDouble(_Symbol, SYMBOL_POINT))
         return;
   }

   int n = ArraySize(g_zones);
   ArrayResize(g_zones, n + 1);
   g_zones[n] = z;
}

//+------------------------------------------------------------------+
//| Keep only the most recent N zones                                  |
//+------------------------------------------------------------------+
void TrimZones(int max)
{
   if(ArraySize(g_zones) <= max) return;

   // Sort by time_start descending (newest first)
   for(int i = 0; i < ArraySize(g_zones) - 1; i++)
   {
      for(int j = i + 1; j < ArraySize(g_zones); j++)
      {
         if(g_zones[j].time_start > g_zones[i].time_start)
         {
            SLiquidityZone tmp = g_zones[i];
            g_zones[i] = g_zones[j];
            g_zones[j] = tmp;
         }
      }
   }
   ArrayResize(g_zones, max);
}

//+------------------------------------------------------------------+
//| Draw zones as rectangles on chart                                 |
//+------------------------------------------------------------------+
void DrawZones()
{
   ObjectsDeleteAll(0, "LZ_");

   datetime rightEdge = iTime(_Symbol, Period(), 0) + PeriodSeconds() * 50;

   for(int i = 0; i < ArraySize(g_zones); i++)
   {
      string name = StringFormat("LZ_%s_%d", ZoneTypeToString(g_zones[i].type), i);
      color clr = ColorForZone(g_zones[i].type);

      if(ObjectFind(0, name) < 0)
         ObjectCreate(0, name, OBJ_RECTANGLE, 0,
                      g_zones[i].time_start, g_zones[i].price_high,
                      rightEdge, g_zones[i].price_low);

      ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
      ObjectSetInteger(0, name, OBJPROP_FILL, true);
      ObjectSetInteger(0, name, OBJPROP_BACK, true);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetString(0, name, OBJPROP_TEXT,
                      StringFormat("%s @ %.5f", ZoneTypeToString(g_zones[i].type), g_zones[i].midpoint));
   }
   ChartRedraw(0);
}

color ColorForZone(ENUM_ZONE_TYPE zt)
{
   switch(zt)
   {
      case ZONE_SWING_HIGH: return InpColorSwingHigh;
      case ZONE_SWING_LOW:  return InpColorSwingLow;
      case ZONE_EQUAL_HIGH: return InpColorEqualHigh;
      case ZONE_EQUAL_LOW:  return InpColorEqualLow;
      case ZONE_FVG_BULL:   return InpColorFVGBull;
      case ZONE_FVG_BEAR:   return InpColorFVGBear;
      default:              return clrWhite;
   }
}

//+------------------------------------------------------------------+
//| Publish zones to liquidity-engine via WebRequest                  |
//+------------------------------------------------------------------+
void PublishZones()
{
   if(ArraySize(g_zones) == 0)
   {
      Print("[LiquidityZones] No zones to publish");
      return;
   }

   string timeframe = EnumToString(Period());
   string json = ZonesArrayToJSON(g_zones, _Symbol, timeframe, g_accountID);

   char post[];
   StringToCharArray(json, post, 0, StringLen(json));

   char result[];
   string headers = "Content-Type: application/json\r\n";
   string resultHeaders;

   int timeout = 5000;
   int res = WebRequest(
      "POST",
      g_webhookURL,
      g_webhookPath,    // path
      timeout,
      post,
      0,
      headers,
      result
   );

   int lastError = GetLastError();

   if(res == 200)
   {
      string body = CharArrayToString(result);
      PrintFormat("[LiquidityZones] Published %d zones to %s%s (status=%d)",
                  ArraySize(g_zones), g_webhookURL, g_webhookPath, res);
   }
   else
   {
      PrintFormat("[LiquidityZones] WebRequest failed: res=%d lastError=%d",
                  res, lastError);
      if(lastError == 4060)
         Print("[LiquidityZones] TIP: add the URL to MT5 'Allow WebRequest' list (Tools > Options > Expert Advisors)");
   }
}
//+------------------------------------------------------------------+