#!/usr/bin/env python3
import dns.resolver
import dns.message
import dns.query
import time
import argparse
import statistics
import concurrent.futures
import socket
import random
import string
import csv
import os
from datetime import datetime

# List of real domains to test (both popular and less common)
REAL_DOMAINS = [
    "google.com", "facebook.com", "amazon.com", "youtube.com", "twitter.com",
    "instagram.com", "linkedin.com", "reddit.com", "netflix.com", "tiktok.com",
    "wikipedia.org", "github.com", "apple.com", "microsoft.com", "yahoo.com",
    "twitch.tv", "spotify.com", "zoom.us", "ebay.com", "cnn.com",
    "nytimes.com", "bbc.co.uk", "theguardian.com", "wsj.com", "espn.com",
    "imdb.com", "booking.com", "airbnb.com", "uber.com", "lyft.com",
    "nasa.gov", "nih.gov", "stackoverflow.com", "medium.com", "quora.com",
    "craigslist.org", "weather.com", "yelp.com", "tripadvisor.com", "adobe.com"
]

def generate_random_domain(tld=None):
    """Generate a random domain name that likely doesn't exist."""
    length = random.randint(8, 15)
    domain = ''.join(random.choices(string.ascii_lowercase + string.digits + '-', k=length))
    tld = tld or random.choice(['.com', '.net', '.org', '.io', '.co', '.xyz'])
    return f"{domain}{tld}"

def generate_domain_list(real_count=40, random_count=60, include_nonexistent=True):
    """Generate a mix of real and random domain names."""
    domains = []
    
    # Add real domains
    if real_count > 0:
        domains.extend(random.sample(REAL_DOMAINS, min(real_count, len(REAL_DOMAINS))))
    
    # Add random (likely nonexistent) domains
    if include_nonexistent and random_count > 0:
        for _ in range(random_count):
            domains.append(generate_random_domain())
            
    # Shuffle the domains
    random.shuffle(domains)
    return domains

def perform_dns_query(server_ip, domain, record_type="A"):
    """Perform a single DNS query to the specified server using lower-level DNS functions."""
    try:
        # Create a DNS query message
        query = dns.message.make_query(domain, dns.rdatatype.from_text(record_type))
        
        # Measure query time
        start_time = time.time()
        response = dns.query.udp(query, server_ip, timeout=3, port=53)
        end_time = time.time()
        
        success = response.answer != []
        if not success:
            print("Failed resolution ", response)

        return {
            "domain": domain,
            "success": success,
            "time": (end_time - start_time) * 1000,  # Convert to milliseconds
            "has_answer": success
        }
    except Exception as e:
        return {
            "domain": domain,
            "success": False,
            "time": 0,
            "error": str(e)
        }

def run_sequential_benchmark(server, domains, record_type):
    """Run DNS queries sequentially and measure performance."""
    results = []
    
    start_time = time.time()
    for domain in domains:
        result = perform_dns_query(server, domain, record_type)
        results.append(result)
    total_time = time.time() - start_time
    
    return results, total_time

def run_concurrent_benchmark(server, domains, record_type, max_workers=20):
    """Run DNS queries concurrently and measure performance."""
    start_time = time.time()
    results = []
    
    # Limit max_workers to avoid "Too many open files" error
    max_workers = min(max_workers, 50)
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_domain = {
            executor.submit(perform_dns_query, server, domain, record_type): domain 
            for domain in domains
        }
        
        for future in concurrent.futures.as_completed(future_to_domain):
            result = future.result()
            results.append(result)
    
    total_time = time.time() - start_time
    return results, total_time

def print_stats(results, total_time, num_requests, concurrent=False):
    """Print statistics about the benchmark results."""
    successful = sum(1 for r in results if r["success"])
    resolved = sum(1 for r in results if r.get("has_answer", False))
    response_times = [r["time"] for r in results if r["success"]]
    
    if not response_times:
        print("No successful queries!")
        errors = [r.get("error", "Unknown error") for r in results if not r["success"]]
        if errors:
            print(f"Sample error: {errors[0]}")
        return
    
    mode = "concurrent" if concurrent else "sequential"
    print(f"\n--- {mode.upper()} BENCHMARK RESULTS ---")
    print(f"Total time: {total_time:.2f} seconds")
    print(f"Requests per second: {num_requests / total_time:.2f}")
    print(f"Success rate: {successful}/{num_requests} ({successful/num_requests*100:.2f}%)")
    print(f"Resolution rate: {resolved}/{num_requests} ({resolved/num_requests*100:.2f}%)")
    
    print(f"Response time stats (ms):")
    print(f"  Min:     {min(response_times):.2f}")
    print(f"  Max:     {max(response_times):.2f}")
    print(f"  Average: {statistics.mean(response_times):.2f}")
    print(f"  Median:  {statistics.median(response_times):.2f}")
    if len(response_times) > 1:
        print(f"  StdDev:  {statistics.stdev(response_times):.2f}")
    
    # Display sample of fastest and slowest domains
    if len(response_times) > 5:
        sorted_results = sorted([r for r in results if r["success"]], key=lambda x: x["time"])
        print("\nFastest queries:")
        for i in range(min(3, len(sorted_results))):
            print(f"  {sorted_results[i]['domain']}: {sorted_results[i]['time']:.2f}ms")
        
        print("\nSlowest queries:")
        for i in range(min(3, len(sorted_results))):
            idx = len(sorted_results) - i - 1
            print(f"  {sorted_results[idx]['domain']}: {sorted_results[idx]['time']:.2f}ms")

def save_results_to_csv(results, total_time, num_requests, filename=None):
    """Save the benchmark results to a CSV file."""
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"dns_benchmark_{timestamp}.csv"
    
    with open(filename, 'w', newline='') as csvfile:
        fieldnames = ['domain', 'success', 'time_ms', 'has_answer', 'error']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for result in results:
            row = {
                'domain': result['domain'],
                'success': result['success'],
                'time_ms': result['time'] if result['success'] else 0,
                'has_answer': result.get('has_answer', False),
                'error': result.get('error', '') if not result['success'] else ''
            }
            writer.writerow(row)
    
    print(f"\nResults saved to {filename}")
    return filename

def main():
    parser = argparse.ArgumentParser(description="Benchmark a DNS server with multiple domains")
    parser.add_argument("--server", default="127.0.0.1", help="DNS server IP (default: 127.0.0.1)")
    parser.add_argument("--requests", type=int, default=100, help="Number of total requests to send (default: 100)")
    parser.add_argument("--type", default="A", help="Record type to query (default: A)")
    parser.add_argument("--concurrent", action="store_true", help="Run requests concurrently")
    parser.add_argument("--workers", type=int, default=20, help="Max worker threads for concurrent mode (default: 20)")
    parser.add_argument("--sequential-only", action="store_true", help="Only run sequential benchmark")
    parser.add_argument("--real-ratio", type=float, default=0.4, help="Ratio of real domains to use (0.0-1.0, default: 0.4)")
    parser.add_argument("--save-csv", action="store_true", help="Save results to CSV file")
    parser.add_argument("--csv-file", help="Custom filename for CSV results")
    parser.add_argument("--domain-file", help="File containing list of domains to use (one per line)")
    
    args = parser.parse_args()
    
    # Load or generate domain list
    if args.domain_file and os.path.exists(args.domain_file):
        with open(args.domain_file, 'r') as f:
            domains = [line.strip() for line in f if line.strip()]
        print(f"Loaded {len(domains)} domains from {args.domain_file}")
        
        # If we need more domains than provided in the file, generate additional ones
        if len(domains) < args.requests:
            additional = generate_domain_list(
                real_count=0, 
                random_count=args.requests - len(domains)
            )
            domains.extend(additional)
            print(f"Generated {len(additional)} additional random domains")
    else:
        real_count = int(args.requests * args.real_ratio)
        random_count = args.requests - real_count
        domains = generate_domain_list(real_count=real_count, random_count=random_count)
        print(f"Generated domain list with {real_count} real and {random_count} random domains")
    
    # Ensure we have exactly the requested number of domains
    if len(domains) > args.requests:
        domains = domains[:args.requests]
    
    print(f"Benchmarking DNS server at {args.server}:53")
    print(f"Sending {len(domains)} {args.type} queries for {len(set(domains))} unique domains")
    
    # Validate server is reachable before starting
    try:
        socket.gethostbyname(args.server)
    except socket.gaierror:
        print(f"Error: Could not resolve server address '{args.server}'")
        return
    
    all_results = []
    
    if args.concurrent:
        print(f"Running in concurrent mode with {args.workers} workers")
        results, total_time = run_concurrent_benchmark(
            args.server, domains, args.type, args.workers
        )
        print_stats(results, total_time, len(domains), concurrent=True)
        all_results = results
    else:
        print("Running in sequential mode")
        results, total_time = run_sequential_benchmark(
            args.server, domains, args.type
        )
        print_stats(results, total_time, len(domains))
        all_results = results
    
    # Run both modes if not specified
    if not args.concurrent and not args.sequential_only:
        print("\nAlso running concurrent benchmark for comparison...")
        results, total_time = run_concurrent_benchmark(
            args.server, domains, args.type, args.workers
        )
        print_stats(results, total_time, len(domains), concurrent=True)
        all_results = results  # Use the concurrent results for CSV if we ran both
    
    # Save results to CSV if requested
    if args.save_csv:
        save_results_to_csv(all_results, total_time, len(domains), args.csv_file)

if __name__ == "__main__":
    main()



"""
# Basic usage with 100 domains (40 real, 60 random)
python benchmark.py

# Test with 500 domains
python benchmark.py --requests 500

# Use 80% real domains, 20% random
python benchmark.py --real-ratio 0.8

# Use your own domain list
python benchmark.py --domain-file my_domains.txt

# Save results to CSV for further analysis
python benchmark.py --save-csv

# High concurrency test
python benchmark.py --concurrent --workers 40
"""