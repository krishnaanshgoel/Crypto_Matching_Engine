"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import axios from "axios";

export default function Home() {
  const [bidorders, setBidorders] = useState([]);
  const [askorders, setAskorders] = useState([]);
  const [trades, setTrades] = useState([]);
  const [bbo, setBbo] = useState({
    bid: null,
    ask: null,
    bid_size: null,
    ask_size: null,
  });
  // const [ws, setWs] = useState(null);
  // const [marketDataWs, setMarketDataWs] = useState(null);
  // const [tradesWs, setTradesWs] = useState(null);
  // const [ordersWs, setOrdersWs] = useState(null);

  const [symbol, setSymbol] = useState("BTC_USD");
  const [side, setSide] = useState("BUY");
  const [type, setType] = useState("LIMIT");
  const [quantity, setQuantity] = useState("");
  const [price, setPrice] = useState("");
  const [stopPrice, setStopPrice] = useState("");

  const formatDecimalInput = (value) => {
    const num = parseFloat(value);
    if (isNaN(num) || num < 0) return "";
    return num.toFixed(6).replace(/\.?0+$/, ""); // Remove trailing zeros
  };

  // Monitor state changes
  // useEffect(() => {
  //   console.log('Current bidorders:', bidorders);
  //   console.log('Current askorders:', askorders);
  // }, [bidorders, askorders]);

  // WebSocket connections
  // useEffect(() => {
  //   // let marketDataWebSocket = null;
  //   // let tradesWebSocket = null;
  //   // let ordersWebSocket = null;
  //   // let reconnectAttempts = 0;
  //   // const maxReconnectAttempts = 5;
  //   // const reconnectDelay = 3000; // 3 seconds

  //   // const ws = new WebSocket("ws://localhost:8000/api/ws/market-data/BTC-USDT");
  //   //   ws.onmessage = msg => console.log("Received:", msg.data);
  //   //   ws.onopen = () => console.log("WebSocket connected!");
  //   //   ws.onerror = err => console.error("WebSocket error:", err);

  //   // async function getPendingOrders() {
  //   //   try {
  //   //     const res = await axios.get(`http://localhost:8000/pending-orders/${symbol}`);
  //   //     console.log('API Response:', res.data);
        
  //   //     if (res.status === 200 && res.data) {
  //   //       setBidorders(res.data.bids || []);
  //   //       setAskorders(res.data.asks || []);
          
  //   //       // Use useEffect to log state changes
  //   //       console.log('Updated bidorders:', res.data.bids);
  //   //       console.log('Updated askorders:', res.data.asks);
  //   //     }
  //   //   } catch (error) {
  //   //     console.error('Error fetching pending orders:', error);
  //   //   }
  //   // }

  //   // Call getPendingOrders
  //   // getPendingOrders();

  //   // Set up polling to refresh orders every 5 seconds
  // }, [symbol]); // Reconnect when symbol changes



  const formatTimestamp = (timestamp) => {
    const date = new Date(timestamp);
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    });
  };

  const handleSubmit = useCallback(async (e) => {
    e.preventDefault();
    
    const orderData = {
      symbol,
      side,
      order_type: type,
      quantity: parseFloat(quantity),
      price: ["LIMIT", "STOP_LIMIT","IOC","FOK","TAKE_PROFIT"].includes(type) ? parseFloat(price) : null,
      stop_price: ["STOP_LOSS", "STOP_LIMIT", "TAKE_PROFIT"].includes(type) ? parseFloat(stopPrice) : null
    };
    console.log('Order data:', orderData);

    try {
      const response = await axios.post('http://localhost:8000/api/v1/orders', orderData);
      if(response.status === 200) {
        console.log('Order submitted:', response);
        if(response.data.trades && Array.isArray(response.data.trades)) {
          setTrades(prev => [...response.data.trades, ...prev]);
        }
      }
      
      const result = await axios.get('http://localhost:8000/api/v1/market-data/BTC-USD');
      if(result.status === 200) {
        console.log('Market data:', result.data);
        setBbo({
          bid: result.data.bbo.best_bid_price,
          ask: result.data.bbo.best_ask_price,
          bid_size: result.data.bbo.best_bid_quantity,
          ask_size: result.data.bbo.best_ask_quantity,
        });
      }
      // Clear form
      setQuantity("");
      setPrice("");
      setStopPrice("");
      
      // Fetch updated orders after submission
      const res = await axios.get(`http://localhost:8000/api/v1/pending-orders/${symbol}`);
      setBidorders(res.data.bids || []);
      setAskorders(res.data.asks || []);
    } catch (error) {
      console.error('Error submitting order:', error);
    }
  }, [symbol, side, type, quantity, price, stopPrice]);

  useEffect(() => {
    const fetchOrders = async () => {
      try {
        // const res = await axios.get(`http://localhost:8000/api/v1/pending-orders/${symbol}`);
        // console.log(res.data);
        // setBidorders(res.data.bids || []);
        // setAskorders(res.data.asks || []);
        // const result = await axios.get('http://localhost:8000/api/v1/market-data/BTC-USD');
        // if(result.status === 200) {
        //   setBbo({
        //     bid: result.data.bbo.best_bid_price,
        //     ask: result.data.bbo.best_ask_price,
        //     bid_size: result.data.bbo.best_bid_quantity,
        //     ask_size: result.data.bbo.best_ask_quantity,
        //   });
        // }
        // const ws=new WebSocket(`ws://localhost:8000/api/ws/market-data/${symbol}`);
        ws.onmessage=msg=>{
          const data=JSON.parse(msg.data);
          console.log(data);
          setBidorders(data.data.bids || []);
          setAskorders(data.data.asks || []);
          setBbo({
            bid: data.bbo.best_bid,
            ask: data.bbo.best_ask,
            bid_size: data.bbo.best_bid_quantity,
            ask_size: data.bbo.best_ask_quantity,
          })
        }
        ws.onopen=()=>{
          console.log("WebSocket connected!");
        }
      } catch (error) {
        console.error('Error fetching pending orders:', error);
      }
    };
    
    fetchOrders();
    // console.log(trades);
    // console.log(bbo);
    // Set up polling to refresh orders every 5 seconds
    // const intervalId = setInterval(fetchOrders, 5000);
    
    // // Cleanup interval on component unmount or when symbol changes
    // return () => clearInterval(intervalId);
  }, [symbol]);

  return (
    <main className="flex min-h-screen flex-col items-center justify-between p-24">
      <div className="z-10 max-w-5xl w-full items-center justify-between font-mono text-sm">
        <h1 className="text-4xl font-bold mb-8">Trading Interface</h1>
        
        {/* Order Form */}
        <form  className="mb-8">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block mb-2 mr-4">Symbol</label>
              <Select value={symbol} onValueChange={setSymbol}>
                <SelectTrigger>
                  <SelectValue placeholder="Select symbol" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="BTC_USD">BTC-USDT</SelectItem>
                  
                  <SelectItem value="BT-USD">ETH-USDT</SelectItem>
                </SelectContent>
              </Select>
            </div>
            
            <div className="">
              <label className="block mb-2">Side</label>
              <Select value={side} onValueChange={setSide} className="">
                <SelectTrigger>
                  <SelectValue placeholder="Select side" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="BUY">Buy</SelectItem>
                  <SelectItem value="SELL">Sell</SelectItem>
                </SelectContent>
              </Select>
            </div>
            
            <div>
              <label className="block mb-2">Type</label>
              <Select value={type} onValueChange={setType}>
                <SelectTrigger>
                  <SelectValue placeholder="Select type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="MARKET">Market</SelectItem>
                  <SelectItem value="LIMIT">Limit</SelectItem>
                  <SelectItem value="STOP_LOSS">Stop-Loss</SelectItem>
                  <SelectItem value="STOP_LIMIT">Stop-Limit</SelectItem>
                  <SelectItem value="TAKE_PROFIT">Take-Profit</SelectItem>
                  <SelectItem value="IOC">IOC</SelectItem>
                  <SelectItem value="FOK">FOK</SelectItem>
                </SelectContent>
              </Select>
            </div>
            
            <div>
              <label className="block mb-2">Quantity</label>
              <Input
                type="number"
                value={quantity}
                onChange={(e) => setQuantity(formatDecimalInput(e.target.value))}
                placeholder="Enter quantity"
                required
              />
            </div>
            
            {["LIMIT", "STOP_LIMIT","IOC","FOK"].includes(type) && (
              <div>
                <label className="block mb-2">Price</label>
                <Input
                  type="number"
                  value={price}
                  onChange={(e) => setPrice(formatDecimalInput(e.target.value))}
                  placeholder="Enter price"
                  required
                />
              </div>
            )}

            {["STOP_LOSS", "STOP_LIMIT", "TAKE_PROFIT"].includes(type) && (
              <div>
                <label className="block mb-2">Stop Price</label>
                <Input
                  type="number"
                  value={stopPrice}
                  onChange={(e) => setStopPrice(formatDecimalInput(e.target.value))}
                  placeholder="Enter stop price"
                  required
                />
              </div>
            )}
          </div>
          
          <Button type="submit" className="mt-4" onClick={handleSubmit}>
            Submit Order
          </Button>
        </form>

        {/* Order Book */}
        <div className="mb-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-green-100 p-4 rounded-lg">
              <h3 className="text-lg font-semibold text-green-800">Best Bid</h3>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <p className="text-sm text-green-600">Price</p>
                  <p className="text-xl font-bold">{bbo.bid || '-'}</p>
                </div>
                <div>
                  <p className="text-sm text-green-600">Quantity</p>
                  <p className="text-xl font-bold">{bbo.bid_size || '-'}</p>
                </div>
              </div>
            </div>
            <div className="bg-red-100 p-4 rounded-lg">
              <h3 className="text-lg font-semibold text-red-800">Best Ask</h3>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <p className="text-sm text-red-600">Price</p>
                  <p className="text-xl font-bold">{bbo.ask || '-'}</p>
                </div>
                <div>
                  <p className="text-sm text-red-600">Quantity</p>
                  <p className="text-xl font-bold">{bbo.ask_size || '-'}</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Order Book */}
        <Table className="table-fixed w-full border-2 border-black">
          <TableCaption>OrderBook</TableCaption>
          <TableHeader className="border-black">
            <TableRow className="border-black">
              <TableHead colSpan={3} className="text-center text-xl font-bold border-r-2 border-black">
                Bids
              </TableHead>
              <TableHead colSpan={3} className="text-center text-xl font-bold">
                Asks
              </TableHead>
            </TableRow>
            <TableRow className="border-black">
              {/* Bids */}
              <TableHead className="text-center font-semibold w-[150px] bg-green-100 border-r border-black">Time</TableHead>
              <TableHead className="text-center font-semibold w-[100px] bg-green-100 border-r border-black">Price</TableHead>
              <TableHead className="text-center font-semibold w-[100px] bg-green-100 border-r-2 border-black">Qty</TableHead>
              {/* Asks */}
              <TableHead className="text-center font-semibold w-[150px] bg-red-100 border-r border-black">Time</TableHead>
              <TableHead className="text-center font-semibold w-[100px] bg-red-100 border-r border-black">Price</TableHead>
              <TableHead className="text-center font-semibold w-[100px] bg-red-100">Qty</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(() => {
              // Flatten bid and ask orders
              const flatBids = bidorders.flatMap(bid =>
                bid.orders.map(order => ({ ...order, price: bid.price }))
              );
              const flatAsks = askorders.flatMap(ask =>
                ask.orders.map(order => ({ ...order, price: ask.price }))
              );

              // Max 10 rows total, fill with nulls to pair
              const maxRows = 10;
              const rows = Array.from({ length: Math.min(maxRows,Math.max(flatBids.length,flatAsks.length)) }, (_, i) => ({
                bid: flatBids[i] || null,
                ask: flatAsks[i] || null
              }));

              return rows.map((row, i) => (
                <TableRow key={i} className="border-black">
                  {/* Bid Cells */}
                  {row.bid ? (
                    <>
                      <TableCell className="text-center w-[150px] bg-green-100 border-r border-black">
                        {formatTimestamp(row.bid.timestamp)}
                      </TableCell>
                      <TableCell className="text-center w-[100px] bg-green-100 border-r border-black">
                        {row.bid.price}
                      </TableCell>
                      <TableCell className="text-center w-[100px] bg-green-100 border-r-2 border-black">
                        {row.bid.quantity}
                      </TableCell>
                    </>
                  ) : (
                    <>
                      <TableCell className="w-[150px] bg-green-100 border-r border-black" />
                      <TableCell className="w-[100px] bg-green-100 border-r border-black" />
                      <TableCell className="w-[100px] bg-green-100 border-r-2 border-black" />
                    </>
                  )}

                  {/* Ask Cells */}
                  {row.ask ? (
                    <>
                      <TableCell className="text-center w-[150px] bg-red-100 border-r border-black">
                        {formatTimestamp(row.ask.timestamp)}
                      </TableCell>
                      <TableCell className="text-center w-[100px] bg-red-100 border-r border-black">
                        {row.ask.price}
                      </TableCell>
                      <TableCell className="text-center w-[100px] bg-red-100">
                        {row.ask.quantity}
                      </TableCell>
                    </>
                  ) : (
                    <>
                      <TableCell className="w-[150px] bg-red-100 border-r border-black" />
                      <TableCell className="w-[100px] bg-red-100 border-r border-black" />
                      <TableCell className="w-[100px] bg-red-100" />
                    </>
                  )}
                </TableRow>
              ));
            })()}
          </TableBody>
        </Table>


        {/* Recent Trades */}
        <div className="mt-8">
          <h2 className="text-2xl font-bold mb-4">Recent Trades</h2>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-center">Time</TableHead>
                <TableHead className="text-center">Price</TableHead>
                <TableHead className="text-center">Quantity</TableHead>
                <TableHead className="text-center">Trade ID</TableHead>
                <TableHead className="text-center">Agressor Side</TableHead>
                <TableHead className="text-center">Buy order id</TableHead>
                <TableHead className="text-center">Sell order id</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {trades.slice(0, 10).map((trade, index) => (
                <TableRow key={index} className={`${trade.side === 'BUY' ? 'bg-green-100' : 'bg-red-100'}`}>
                  <TableCell className="text-center">{formatTimestamp(trade.timestamp)}</TableCell>
                  <TableCell className="text-center">{trade.price}</TableCell>
                  <TableCell className="text-center">{trade.quantity}</TableCell>
                  <TableCell className="text-center">{trade.id}</TableCell>
                  <TableCell className="text-center">{trade.side}</TableCell>
                  <TableCell className="text-center">{trade.buy_order_id}</TableCell>
                  <TableCell className="text-center">{trade.sell_order_id}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </div>
    </main>
  );
}
/** 
<Table>
  <TableCaption>your orders</TableCaption>
  <TableHeader>
    <TableRow>
      <TableHead colspan={3} className=""text-2xl font-bold mb-4"">Bids</TableHead>
      <TableHead colspan={3} className=""text-2xl font-bold mb-4"">Asks</TableHead>
    </TableRow>
    <TableRow>
    <TableHead>Timestamp</TableHead>
      <TableHead>Price</TableHead>
      <TableHead>Quantity</TableHead>
      <TableHead>Timestamp</TableHead>
      <TableHead>Price</TableHead>
      <TableHead>Quantity</TableHead>
    </TableRow>
  </TableHeader>
  <TableBody>
  {bidorders?.slice(0, Math.min(10, bidorders.length)).map((bid, index) => (
    <TableRow>
                <div key={index} className="flex justify-between">
                  <TableCell>{formatTimestamp(bid.timestamp)}</TableCell>
                  <TableCell>{bid.price}</TableCell>
                  <TableCell>{bid.quantity}</TableCell>
                </div>
    </TableRow>
              ))}
    
  </TableBody>
</Table> 



 */
/*
<Table className="table-fixed w-full border-2 border-black">
<TableCaption>OrderBook</TableCaption>
<TableHeader className="border-black">
  <TableRow className="border-black">
    <TableHead colSpan={3} className="text-center text-xl font-bold border-r-2 border-black">
      Bids
    </TableHead>
    <TableHead colSpan={3} className="text-center text-xl font-bold">
      Asks
    </TableHead>
  </TableRow>
  <TableRow className="border-black">
    {/* Bids *//*}
    <TableHead className="text-center font-semibold w-[150px] bg-green-100 border-r border-black">Time</TableHead>
    <TableHead className="text-center font-semibold w-[100px] bg-green-100 border-r border-black">Price</TableHead>
    <TableHead className="text-center font-semibold w-[100px] bg-green-100 border-r-2 border-black">Qty</TableHead>

    {/* Asks *//*}
    <TableHead className="text-center font-semibold w-[150px] bg-red-100 border-r border-black">Time</TableHead>
    <TableHead className="text-center font-semibold w-[100px] bg-red-100 border-r border-black">Price</TableHead>
    <TableHead className="text-center font-semibold w-[100px] bg-red-100">Qty</TableHead>
  </TableRow>
</TableHeader>
<TableBody>
  {Array.from({
    length: Math.min(Math.max(bidorders.length, askorders.length),10),
  }).map((_, i) => (
    <TableRow key={i} className="border-black">
      {/* Bid Row *//*}
      {bidorders[i] ? (
        <>
          <TableCell className="text-center w-[150px] bg-green-100 border-r border-black">
            {formatTimestamp(bidorders[i].orders[0].timestamp)}
          </TableCell>
          <TableCell className="text-center w-[100px] bg-green-100 border-r border-black">
            {bidorders[i].price}
          </TableCell>
          <TableCell className="text-center w-[100px] bg-green-100 border-r-2 border-black">
            {bidorders[i].quantity}
          </TableCell>
        </>
      ) : (
        <>
          <TableCell className="w-[150px] bg-green-100 border-r border-black" />
          <TableCell className="w-[100px] bg-green-100 border-r border-black" />
          <TableCell className="w-[100px] bg-green-100 border-r-2 border-black" />
        </>
      )}

      {/* Ask Row *//*  }
      {askorders[i] ? (
        <>
          <TableCell className="text-center w-[150px] bg-red-100 border-r border-black">
            {formatTimestamp(askorders[i].orders[0].timestamp)}
          </TableCell>
          <TableCell className="text-center w-[100px] bg-red-100 border-r border-black">
            {askorders[i].price}
          </TableCell>
          <TableCell className="text-center w-[100px] bg-red-100">
            {askorders[i].quantity}
          </TableCell>
        </>
      ) : (
        <>
          <TableCell className="w-[150px] bg-red-100 border-r border-black" />
          <TableCell className="w-[100px] bg-red-100 border-r border-black" />
          <TableCell className="w-[100px] bg-red-100" />
        </>
      )}
    </TableRow>
  ))}
</TableBody>
</Table>
*/