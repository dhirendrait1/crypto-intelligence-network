import { useState } from "react";

export type WatchlistProduct = "BTC-USD" | "ETH-USD";

interface MarketWatchlistProps {
  selectedProduct: WatchlistProduct;
  onSelect: (product: WatchlistProduct) => void;
  disabled?: boolean;
}

const supportedProducts: { id: WatchlistProduct; label: string; name: string }[] = [
  { id: "BTC-USD", label: "BTC", name: "Bitcoin" },
  { id: "ETH-USD", label: "ETH", name: "Ethereum" },
];

export function MarketWatchlist({ selectedProduct, onSelect, disabled = false }: MarketWatchlistProps) {
  const [pinned, setPinned] = useState<WatchlistProduct[]>(["BTC-USD", "ETH-USD"]);

  function toggle(product: WatchlistProduct) {
    if (pinned.includes(product)) {
      if (pinned.length === 1) return;
      const next = pinned.filter((item) => item !== product);
      setPinned(next);
      if (selectedProduct === product) onSelect(next[0]);
      return;
    }
    setPinned([...pinned, product]);
  }

  return (
    <section className="market-watchlist" aria-label="Market watchlist">
      <div className="market-watchlist-heading">
        <div><span className="eyebrow">QUICK ACCESS</span><strong>Session watchlist</strong></div>
        <span>{pinned.length} pinned</span>
      </div>
      <div className="market-watchlist-items">
        {pinned.map((product) => {
          const item = supportedProducts.find((candidate) => candidate.id === product)!;
          return <button key={product} type="button" className={selectedProduct === product ? "watchlist-item watchlist-active" : "watchlist-item"} aria-pressed={selectedProduct === product} onClick={() => onSelect(product)} disabled={disabled}>
            <span className="watchlist-symbol">{item.label}</span><span className="watchlist-name">{item.name}</span><span className="watchlist-selected">{selectedProduct === product ? "Selected" : "View"}</span>
          </button>;
        })}
      </div>
      <div className="market-watchlist-manage">
        <span>Supported Coinbase USD markets</span>
        {supportedProducts.map((product) => <button key={product.id} type="button" onClick={() => toggle(product.id)} disabled={disabled || pinned.includes(product.id) && pinned.length === 1} aria-label={`${pinned.includes(product.id) ? "Remove" : "Add"} ${product.id} ${pinned.includes(product.id) ? "from" : "to"} watchlist`}>
          {pinned.includes(product.id) ? `− ${product.label}` : `+ ${product.label}`}
        </button>)}
      </div>
      <p className="markets-footnote">Pins are kept for this screen session only. Selecting a market does not request data; use Load candles to fetch observations.</p>
    </section>
  );
}
