// You can edit this code!
// Click here and start typing.
package main

import "fmt"

func main() {
	var w int
	d := new(int)
	fmt.Println(d)
	d = &w
	fmt.Println(d)
	var t []int
	t = []int{3, 4, 5}
	fmt.Printf("%p %v", t, t) //%v is used for any convert to any type for that use or as it is print purpose also
	t = append(t, 6)
	fmt.Println()
	fmt.Printf("%p,%v", t, t)
	fmt.Println()
	var e *[]int
	e = &[]int{1, 2, 3}

	fmt.Print(*e, &e)
	*e = append(*e, 2)
	fmt.Println(*e, &e)

	type b map[any]any
	var y b
	fmt.Println(len(y), y == nil)//dfef

}
