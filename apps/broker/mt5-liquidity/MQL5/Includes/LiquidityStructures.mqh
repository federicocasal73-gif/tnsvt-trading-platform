//+------------------------------------------------------------------+
//|                                       LiquidityStructures.mqh     |
//|                       TNSVT - Terminal Financiera Pro             |
//|                                                                   |
//|  Defines:                                                          |
//|   - ELiquidityZone: swing high/low, equal high/low, FVG            |
//|   - EZoneType: enum of zone kinds                                 |
//|   - Helper functions for JSON serialization                       |
//+------------------------------------------------------------------+
#property copyright "TNSVT"
#property version   "1.00"
#property strict

#ifndef LIQUIDITY_STRUCTURES_MQH
#define LIQUIDITY_STRUCTURES_MQH

//--- Zone types
enum ENUM_ZONE_TYPE
{
   ZONE_SWING_HIGH    = 0,
   ZONE_SWING_LOW     = 1,
   ZONE_EQUAL_HIGH    = 2,
   ZONE_EQUAL_LOW     = 3,
   ZONE_FVG_BULL      = 4,   // bullish fair value gap (3-candle imbalance)
   ZONE_FVG_BEAR      = 5,   // bearish fair value gap
   ZONE_BOS_BULL      = 6,   // break of structure bullish
   ZONE_BOS_BEAR      = 7,   // break of structure bearish
};

//--- Liquidity zone (single rectangle on chart)
struct SLiquidityZone
{
   ENUM_ZONE_TYPE type;
   double         price_high;     // top of zone
   double         price_low;      // bottom of zone
   datetime       time_start;     // when zone formed
   datetime       time_end;       // right edge (extends forward when touched)
   int            strength;       // number of touches / confluence
   bool           swept;          // has been swept (mitigated)
   double         midpoint;       // computed midpoint
};

//--- Convert ENUM_ZONE_TYPE to string
string ZoneTypeToString(ENUM_ZONE_TYPE zt)
{
   switch(zt)
   {
      case ZONE_SWING_HIGH: return "swing_high";
      case ZONE_SWING_LOW:  return "swing_low";
      case ZONE_EQUAL_HIGH: return "equal_high";
      case ZONE_EQUAL_LOW:  return "equal_low";
      case ZONE_FVG_BULL:   return "fvg_bull";
      case ZONE_FVG_BEAR:   return "fvg_bear";
      case ZONE_BOS_BULL:   return "bos_bull";
      case ZONE_BOS_BEAR:   return "bos_bear";
      default:              return "unknown";
   }
}

//--- Compute midpoint
double ZoneMidpoint(const SLiquidityZone &zone)
{
   return (zone.price_high + zone.price_low) / 2.0;
}

//--- Initialize zone with computed midpoint
void InitZone(SLiquidityZone &zone)
{
   zone.midpoint = ZoneMidpoint(zone);
   if(zone.time_end == 0) zone.time_end = zone.time_start;
   if(zone.strength < 1) zone.strength = 1;
}

//--- Format a zone as JSON snippet (single line)
string ZoneToJSON(const SLiquidityZone &zone, const string &symbol, const string &timeframe)
{
   string json = "";
   json += StringFormat(
      "{\"symbol\":\"%s\",\"timeframe\":\"%s\",\"type\":\"%s\","
      "\"price_high\":%.5f,\"price_low\":%.5f,\"midpoint\":%.5f,"
      "\"time_start\":%d,\"time_end\":%d,\"strength\":%d,\"swept\":%s}",
      symbol,
      timeframe,
      ZoneTypeToString(zone.type),
      zone.price_high,
      zone.price_low,
      zone.midpoint,
      (int)zone.time_start,
      (int)zone.time_end,
      zone.strength,
      zone.swept ? "true" : "false"
   );
   return json;
}

//--- Format multiple zones as full JSON array
string ZonesArrayToJSON(const SLiquidityZone &zones[], const string &symbol,
                        const string &timeframe, const string &account_id)
{
   string json = StringFormat(
      "{\"account_id\":\"%s\",\"symbol\":\"%s\",\"timeframe\":\"%s\","
      "\"ts\":%d,\"count\":%d,\"zones\":[",
      account_id, symbol, timeframe,
      (int)TimeCurrent(),
      ArraySize(zones)
   );

   for(int i = 0; i < ArraySize(zones); i++)
   {
      if(i > 0) json += ",";
      json += ZoneToJSON(zones[i], symbol, timeframe);
   }
   json += "]}";
   return json;
}

//--- Detect if two price levels are "equal" within tolerance (in points)
bool AreEqualLevels(double a, double b, double tolerance_points)
{
   double diff = MathAbs(a - b);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if(point <= 0) point = 0.00001;
   double tolerance = tolerance_points * point;
   return diff <= tolerance;
}

#endif // LIQUIDITY_STRUCTURES_MQH
//+------------------------------------------------------------------+