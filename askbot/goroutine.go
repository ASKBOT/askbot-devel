package main

import (
	"fmt"
	"sync"
	"time"
)

func fes(a string) {
	for i := len(a); i < 10; i++ {
		fmt.Println(i)
	}

}
func main() {
	var wg sync.WaitGroup
	go fes("cv")
	time.Sleep(2) //for all go func we have to give time or sync.waitgroup
	fmt.Println(434)
	go fes("vf") //all runs at a time so we have to give sleep to wait then it will execute
	time.Sleep(5)
	wg.Add(4)
	defer wg.Done()
	fmt.Println(5556) //very line async execute and after one oscilllation wait for 4 sec then again execute
	go fes("f")
	fmt.Println(444)

	go fes("fd")
	wg.Wait()

}
